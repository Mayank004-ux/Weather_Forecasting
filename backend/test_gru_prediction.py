import numpy as np
import pandas as pd

from backend.model_loader import scaler
from backend.feature_engineering import create_features, FEATURE_COLUMNS

from tensorflow.keras.models import load_model


DATA_PATH = "data/raw/Weather_Forecasting.csv"
MODEL_PATH = "models/gru.keras"

CITIES = [
    "Delhi",
    "Mumbai",
    "Bengaluru",
    "Chennai",
    "Bhopal"
]


# Load dataset
df = pd.read_csv(DATA_PATH)

# Load GRU model
gru_model = load_model(MODEL_PATH)


print("=" * 60)
print("GRU PREDICTION TEST - ALL 5 CITIES")
print("=" * 60)

results = []


for city in CITIES:

    print(f"\nTesting: {city}")

    # Select city data
    city_df = df[df["city"] == city].copy()

    print("Rows:", len(city_df))

    # Create the same features used during training
    featured_df = create_features(city_df)

    # Remove rows where lag/rolling features are incomplete
    featured_df = featured_df.dropna(
        subset=FEATURE_COLUMNS
    ).copy()

    # Take the latest 24 hours
    latest_24 = featured_df.tail(24).copy()

    if len(latest_24) != 24:
        print("ERROR: Could not create 24 complete hourly records.")
        continue

    # Select the exact 25 features
    X = latest_24[FEATURE_COLUMNS].values

    print("Original input shape:", X.shape)

    # Scale using the scaler used during training
    X_scaled = scaler.transform(X)

    print("Scaled input shape:", X_scaled.shape)

    # Convert to GRU sequence shape
    X_sequence = X_scaled.reshape(
        1,
        24,
        25
    )

    print("GRU input shape:", X_sequence.shape)

    # Predict
    prediction = gru_model.predict(
        X_sequence,
        verbose=0
    )[0][0]

    last_time = latest_24["time"].iloc[-1]
    last_temperature = latest_24["temperature_2m"].iloc[-1]

    print("Last historical time:", last_time)
    print(
        "Last recorded temperature:",
        last_temperature,
        "°C"
    )

    print(
        "Predicted next-hour temperature:",
        round(float(prediction), 2),
        "°C"
    )

    results.append({
        "city": city,
        "last_time": str(last_time),
        "last_temperature": round(float(last_temperature), 2),
        "predicted_temperature": round(float(prediction), 2)
    })


# Final summary
print("\n")
print("=" * 60)
print("GRU PREDICTION SUMMARY")
print("=" * 60)

results_df = pd.DataFrame(results)

print(results_df.to_string(index=False))

print("=" * 60)
print("GRU TEST COMPLETED")
print("=" * 60)