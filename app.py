
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    jwt_required,
    create_access_token,
    get_jwt_identity,
    get_jwt
)

from database import get_db_connection
from prediction import predict_water_risk
from alerts import generate_alert
from auth import auth_bp

from config import SECRET_KEY, JWT_SECRET_KEY

import math

app = Flask(__name__)

# ROLE-BASED ACCESS CONTROL


from functools import wraps

# ROLE-BASED ACCESS CONTROL
def role_required(*allowed_roles):

    def decorator(func):

        @wraps(func)
        @jwt_required()
        def wrapper(*args, **kwargs):

            user_role = get_jwt().get("role")
            print("DEBUG USER ROLE:", user_role)

            if user_role not in allowed_roles:
                return jsonify({
                    "error": "Access denied. You do not have permission."
                }), 403

            return func(*args, **kwargs)

        return wrapper

    return decorator


app.config["SECRET_KEY"] = SECRET_KEY
app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY

CORS(app)
jwt = JWTManager(app)

# Register authentication APIs
app.register_blueprint(auth_bp)


# Home route
@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "message": "Smart Community Health Monitoring API is running"
    })


# Submit water quality data

@app.route("/submit-water-data", methods=["POST"])
@role_required("community_user","health_worker", "admin")
def submit_water_data():

    data = request.get_json(silent=True) or {}

    required_fields = [
        "location", "ph", "turbidity",
        "temperature", "tds"
    ]

    for field in required_fields:
        if field not in data:
            return jsonify({
                "error": f"Missing field: {field}"
            }), 400

    try:
        location = data["location"]

        if not isinstance(location, str) or not location.strip():
            return jsonify({"error": "Invalid location"}), 400

        location = location.strip()

        if len(location) > 150:
            return jsonify({"error": "Location is too long"}), 400

        ph = float(data["ph"])
        turbidity = float(data["turbidity"])
        temperature = float(data["temperature"])
        tds = float(data["tds"])

        # Rainfall is optional; default is 0 mm
        rainfall_mm = float(data.get("rainfall_mm", 0))

        values = [
            ph, turbidity, temperature, tds, rainfall_mm
        ]

        if not all(math.isfinite(v) for v in values):
            return jsonify({"error": "Invalid numeric values"}), 400

        if not 0 <= ph <= 14:
            return jsonify({"error": "Invalid pH value"}), 400

        if turbidity < 0 or tds < 0:
            return jsonify({
                "error": "Turbidity and TDS cannot be negative"
            }), 400

        if rainfall_mm < 0:
            return jsonify({
                "error": "Rainfall cannot be negative"
            }), 400

        if not -10 <= temperature <= 100:
            return jsonify({"error": "Invalid temperature"}), 400

    except (ValueError, TypeError):
        return jsonify({
            "error": "Enter valid numerical values"
        }), 400

    # Step 1: Predict risk using existing ML model
    prediction = predict_water_risk(
        ph, turbidity, temperature, tds
    )

    risk = prediction["risk_level"]

    # Step 2: Generate alert
    alert = generate_alert(
        location,
        risk,
        prediction["reasons"]
    )

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Step 3: Save water quality and rainfall information
        cursor.execute(
            """
            INSERT INTO water_quality
            (location, ph, turbidity, temperature,
             tds, rainfall_mm, risk_level, risk_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                location, ph, turbidity,
                temperature, tds, rainfall_mm,
                risk, prediction["risk_score"]
            )
        )

        record_id = cursor.lastrowid

        # Step 4: Save alert if necessary
        if alert:
            cursor.execute(
                """
                INSERT INTO alerts
                (location, risk_level, message)
                VALUES (%s, %s, %s)
                """,
                (
                    location,
                    risk,
                    alert["message"]
                )
            )

        connection.commit()

        return jsonify({
            "message": "Water quality data saved successfully",
            "record_id": record_id,
            "rainfall_mm": rainfall_mm,
            "prediction": prediction,
            "alert": alert
        }), 201

    except Exception:
        connection.rollback()
        app.logger.exception("Failed to save water data")

        return jsonify({
            "error": "Unable to save water quality data"
        }), 500

    finally:
        cursor.close()
        connection.close()



# View water quality history
@app.route("/get-history", methods=["GET"])
@jwt_required()
def get_history():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT * FROM water_quality
            ORDER BY created_at DESC
            LIMIT 200
            """
        )

        records = cursor.fetchall()

        for record in records:
            record["created_at"] = record["created_at"].isoformat()

        return jsonify(records)

    finally:
        cursor.close()
        connection.close()


# View early warning alerts
@app.route("/get-alerts", methods=["GET"])
@jwt_required()
def get_alerts():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT * FROM alerts
            ORDER BY created_at DESC
            LIMIT 200
            """
        )

        alerts = cursor.fetchall()

        for alert in alerts:
            alert["created_at"] = alert["created_at"].isoformat()

        return jsonify(alerts)

    finally:
        cursor.close()
        connection.close()


# Community-wise risk summary
@app.route("/get-community-status", methods=["GET"])
@jwt_required()
def get_community_status():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                location,
                COUNT(*) AS total_samples,
                MAX(created_at) AS last_updated,
                SUM(CASE WHEN risk_level = 'High'
                    THEN 1 ELSE 0 END) AS high_risk_samples
            FROM water_quality
            GROUP BY location
            ORDER BY high_risk_samples DESC
            """
        )

        results = cursor.fetchall()

        for row in results:
            row["last_updated"] = (
                row["last_updated"].isoformat()
                if row["last_updated"] else None
            )

        return jsonify(results)

    finally:
        cursor.close()
        connection.close()


# ---------------------------------
# DISEASE REPORTING APIs
# ---------------------------------

@app.route("/disease-reports", methods=["POST"])
@role_required("health_worker", "admin")
def submit_disease_report():

    data = request.get_json(silent=True) or {}

    location = data.get("location")
    disease_name = data.get("disease_name")
    case_count = data.get("case_count")
    report_date = data.get("report_date")
    remarks = data.get("remarks", "")

    if not location or not disease_name or case_count is None or not report_date:
        return jsonify({
            "error": "Location, disease name, case count and report date are required"
        }), 400

    try:
        case_count = int(case_count)

        if case_count < 0:
            return jsonify({"error": "Case count cannot be negative"}), 400

        from datetime import date
        report_date = date.fromisoformat(report_date)

    except (ValueError, TypeError):
        return jsonify({
            "error": "Invalid case count or report date. Use YYYY-MM-DD."
        }), 400

    user_id = int(get_jwt_identity())

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO disease_reports
            (location, disease_name, case_count, report_date, reported_by, remarks)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            location.strip(),
            disease_name.strip(),
            case_count,
            report_date,
            user_id,
            remarks
        ))

        connection.commit()

        report_id = cursor.lastrowid

        return jsonify({
            "message": "Disease report submitted successfully",
            "report_id": report_id
        }), 201

    finally:
        cursor.close()
        connection.close()


# GET ALL DISEASE REPORTS

@app.route("/disease-reports", methods=["GET"])
@jwt_required()
def get_disease_reports():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                report_id,
                location,
                disease_name,
                case_count,
                report_date,
                reported_by,
                remarks
            FROM disease_reports
            ORDER BY report_date DESC, report_id DESC
        """)

        reports = cursor.fetchall()

        for report in reports:
            report["report_date"] = report["report_date"].isoformat()

        return jsonify(reports), 200

    finally:
        cursor.close()
        connection.close()


# GET INDIVIDUAL DISEASE REPORT

@app.route("/disease-reports/<int:report_id>", methods=["GET"])
@jwt_required()
def get_single_disease_report(report_id):

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT *
            FROM disease_reports
            WHERE report_id = %s
        """, (report_id,))

        report = cursor.fetchone()

        if not report:
            return jsonify({"error": "Report not found"}), 404

        report["report_date"] = report["report_date"].isoformat()

        return jsonify(report), 200

    finally:
        cursor.close()
        connection.close()

# ---------------------------------
# DASHBOARD SUMMARY API
# ---------------------------------

@app.route("/dashboard/summary", methods=["GET"])
@jwt_required()
def dashboard_summary():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Total reported disease cases
        cursor.execute("""
            SELECT COALESCE(SUM(case_count), 0) AS total_reported_cases
            FROM disease_reports
        """)
        cases = cursor.fetchone()

        # Number of monitored villages
        cursor.execute("""
            SELECT COUNT(DISTINCT location) AS villages_monitored
            FROM water_quality
        """)
        villages = cursor.fetchone()

        # Number of high-risk locations
        cursor.execute("""
            SELECT COUNT(*) AS high_risk_locations
            FROM (
                SELECT location
                FROM water_quality
                GROUP BY location
                HAVING MAX(
                    CASE WHEN risk_level = 'High' THEN 1 ELSE 0 END
                ) = 1
            ) AS high_risk
        """)
        high_risk = cursor.fetchone()

        # Risk distribution by location
        cursor.execute("""
            SELECT
                location,
                CASE
                    WHEN MAX(CASE WHEN risk_level = 'High' THEN 1 ELSE 0 END) = 1
                        THEN 'High'
                    WHEN MAX(CASE WHEN risk_level = 'Medium' THEN 1 ELSE 0 END) = 1
                        THEN 'Medium'
                    ELSE 'Low'
                END AS risk_level
            FROM water_quality
            GROUP BY location
        """)
        distribution_rows = cursor.fetchall()

        risk_distribution = {
            "Low": 0,
            "Medium": 0,
            "High": 0
        }

        for row in distribution_rows:
            risk_distribution[row["risk_level"]] += 1

        return jsonify({
            "total_reported_cases": cases["total_reported_cases"],
            "villages_monitored": villages["villages_monitored"],
            "high_risk_locations": high_risk["high_risk_locations"],
            "risk_distribution": risk_distribution
        }), 200

    finally:
        cursor.close()
        connection.close()


# ---------------------------------
# HIGH-RISK LOCATIONS API
# ---------------------------------

@app.route("/dashboard/high-risk-locations", methods=["GET"])
@jwt_required()
def high_risk_locations():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                w.location,
                w.ph,
                w.turbidity,
                w.temperature,
                w.tds,
                w.risk_level,
                w.risk_score,
                w.created_at
            FROM water_quality w
            INNER JOIN (
                SELECT location, MAX(record_id) AS latest_id
                FROM water_quality
                GROUP BY location
            ) latest
            ON w.record_id = latest.latest_id
            WHERE w.risk_level = 'High'
            ORDER BY w.created_at DESC
        """)

        locations = cursor.fetchall()

        for item in locations:
            if item["created_at"]:
                item["created_at"] = item["created_at"].isoformat()

        return jsonify({
            "total_high_risk_locations": len(locations),
            "locations": locations
        }), 200

    finally:
        cursor.close()
        connection.close()

# GEOGRAPHICAL RISK MAP API

@app.route("/map/risk-locations", methods=["GET"])
@jwt_required()
def get_map_risk_locations():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                v.village_name,
                v.district,
                v.state,
                v.latitude,
                v.longitude,
                w.risk_level,
                w.risk_score,
                w.created_at
            FROM villages v
            INNER JOIN (
                SELECT location, MAX(record_id) AS latest_id
                FROM water_quality
                GROUP BY location
            ) latest
                ON v.village_name = latest.location
            INNER JOIN water_quality w
                ON w.record_id = latest.latest_id
            ORDER BY v.village_name
        """)

        locations = cursor.fetchall()

        for item in locations:
            if item["created_at"]:
                item["created_at"] = item["created_at"].isoformat()

        return jsonify({
            "total_locations": len(locations),
            "locations": locations
        }), 200

    finally:
        cursor.close()
        connection.close()

# GOVERNMENT RESPONSE ACTION API

@app.route("/response-actions", methods=["POST"])
@role_required("government_officer", "admin")
def create_response_action():

    data = request.get_json(silent=True) or {}

    location = data.get("location")
    action_description = data.get("action_description", "")

    if not isinstance(location, str) or not location.strip():
        return jsonify({"error": "Valid location is required"}), 400

    if not isinstance(action_description, str):
        return jsonify({"error": "Invalid action description"}), 400

    if len(location.strip()) > 150:
        return jsonify({"error": "Location is too long"}), 400

    village_id = data.get("village_id")
    assigned_officer = data.get("assigned_officer")

    try:
        if village_id is not None:
            village_id = int(village_id)

        if assigned_officer is not None:
            assigned_officer = int(assigned_officer)

    except (ValueError, TypeError):
        return jsonify({"error": "Invalid village or officer ID"}), 400

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO response_actions
            (village_id, location, assigned_officer,
             action_description, status)
            VALUES (%s, %s, %s, %s, 'Reported')
        """, (
            village_id,
            location.strip(),
            assigned_officer,
            action_description.strip()
        ))

        action_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO status_history
            (action_id, previous_status, new_status, updated_by, remarks)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            action_id,
            None,
            "Reported",
            int(get_jwt_identity()),
            "Response action created"
        ))

        connection.commit()

        return jsonify({
            "message": "Response action created successfully",
            "action_id": action_id,
            "status": "Reported"
        }), 201

    except Exception:
        connection.rollback()
        app.logger.exception("Failed to create response action")

        return jsonify({
            "error": "Unable to create response action"
        }), 500

    finally:
        cursor.close()
        connection.close()

# GET ALL RESPONSE ACTIONS

@app.route("/response-actions", methods=["GET"])
@jwt_required()
def get_response_actions():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                action_id,
                village_id,
                location,
                assigned_officer,
                action_description,
                status,
                created_at,
                updated_at
            FROM response_actions
            ORDER BY created_at DESC
        """)

        actions = cursor.fetchall()

        for action in actions:
            if action["created_at"]:
                action["created_at"] = action["created_at"].isoformat()

            if action["updated_at"]:
                action["updated_at"] = action["updated_at"].isoformat()

        return jsonify({
            "total_actions": len(actions),
            "actions": actions
        }), 200

    finally:
        cursor.close()
        connection.close()

# UPDATE RESPONSE ACTION STATUS

@app.route("/response-actions/<int:action_id>/status", methods=["PUT"])
@role_required("government_officer", "admin")
def update_response_status(action_id):

    data = request.get_json(silent=True) or {}

    new_status = data.get("status")
    remarks = data.get("remarks", "")

    allowed_statuses = [
        "Reported",
        "Under Investigation",
        "Action Taken",
        "Monitoring",
        "Resolved"
    ]

    if new_status not in allowed_statuses:
        return jsonify({
            "error": "Invalid status"
        }), 400

    if not isinstance(remarks, str):
        return jsonify({"error": "Invalid remarks"}), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT status
            FROM response_actions
            WHERE action_id = %s
        """, (action_id,))

        action = cursor.fetchone()

        if not action:
            return jsonify({
                "error": "Response action not found"
            }), 404

        old_status = action["status"]

        status_order = {
            "Reported": 0,
            "Under Investigation": 1,
            "Action Taken": 2,
            "Monitoring": 3,
            "Resolved": 4
        }

        if status_order[new_status] != status_order[old_status] + 1:
            return jsonify({
                "error": "Invalid status transition",
                "current_status": old_status,
                "next_expected_status": (
                    allowed_statuses[status_order[old_status] + 1]
                    if old_status in status_order
                    and status_order[old_status] < 4
                    else None
                )
            }), 400

        cursor.execute("""
            UPDATE response_actions
            SET status = %s
            WHERE action_id = %s
        """, (new_status, action_id))

        cursor.execute("""
            INSERT INTO status_history
            (action_id, previous_status, new_status, updated_by, remarks)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            action_id,
            old_status,
            new_status,
            int(get_jwt_identity()),
            remarks
        ))

        connection.commit()

        return jsonify({
            "message": "Status updated successfully",
            "action_id": action_id,
            "previous_status": old_status,
            "new_status": new_status
        }), 200

    except Exception:
        connection.rollback()
        app.logger.exception("Failed to update response status")

        return jsonify({
            "error": "Unable to update status"
        }), 500

    finally:
        cursor.close()
        connection.close()


# GET RESPONSE ACTION STATUS HISTORY

@app.route("/response-actions/<int:action_id>/history", methods=["GET"])
@jwt_required()
def get_response_history(action_id):

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                history_id,
                action_id,
                previous_status,
                new_status,
                updated_by,
                remarks,
                updated_at
            FROM status_history
            WHERE action_id = %s
            ORDER BY updated_at ASC, history_id ASC
        """, (action_id,))

        history = cursor.fetchall()

        for item in history:
            if item["updated_at"]:
                item["updated_at"] = item["updated_at"].isoformat()

        return jsonify({
            "action_id": action_id,
            "total_updates": len(history),
            "history": history
        }), 200

    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
