
import os
import joblib
import pandas as pd

# Locate the trained model
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(
    BASE_DIR, "models", "water_model.joblib"
)

# Load the ML model
model = joblib.load(MODEL_PATH)


def predict_water_risk(ph, turbidity, temperature, tds):

    # Prepare input values
    input_data = pd.DataFrame([{
        "ph": ph,
        "turbidity": turbidity,
        "temperature": temperature,
        "tds": tds
    }])

    # Predict water risk
    prediction = model.predict(input_data)[0]

    # Calculate model confidence
    probabilities = model.predict_proba(input_data)[0]
    confidence = round(max(probabilities) * 100, 2)

    return {
        "risk_level": prediction,
        "risk_score": confidence,
        "reasons": [
            "Prediction generated using the trained ML model"
        ]
    }
