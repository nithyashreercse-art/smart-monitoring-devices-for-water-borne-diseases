
def generate_alert(location, risk_level, reasons):

    if risk_level == "High":

        message = (
            f"URGENT: High water quality risk detected "
            f"in {location}. Immediate confirmatory "
            f"water testing is recommended."
        )

    elif risk_level == "Medium":

        message = (
            f"WARNING: Water quality requires attention "
            f"in {location}. Further testing is recommended."
        )

    else:
        return None

    return {
        "location": location,
        "risk_level": risk_level,
        "message": message,
        "reasons": reasons
    }
