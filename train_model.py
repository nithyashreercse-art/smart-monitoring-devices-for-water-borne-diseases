
import os
import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier

# Sample training dataset
data = {
    "ph": [7.0, 6.8, 5.0, 9.5, 7.2, 4.5, 8.0, 6.5],
    "turbidity": [0.5, 1.0, 8.0, 10.0, 0.8, 9.0, 2.0, 6.0],
    "temperature": [25, 26, 30, 32, 27, 29, 28, 31],
    "tds": [200, 300, 700, 2500, 350, 1800, 450, 900],
    "risk": ["Low", "Low", "High", "High",
             "Low", "High", "Low", "High"]
}

df = pd.DataFrame(data)

# Input and output
X = df[["ph", "turbidity", "temperature", "tds"]]
y = df["risk"]

# Train model
model = RandomForestClassifier(
    n_estimators=100,
    random_state=42
)

model.fit(X, y)

# Create models folder if necessary
os.makedirs("models", exist_ok=True)

# Save trained model
joblib.dump(model, "models/water_model.joblib")

print("Model trained and saved successfully!")
