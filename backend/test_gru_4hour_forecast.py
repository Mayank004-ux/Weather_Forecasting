import numpy as np
import pandas as pd
import requests

from tensorflow.keras.models import load_model

from backend.model_loader import scaler
from backend.feature_engineering import create_features, FEATURE_COLUMNS


# ============================================================
# CONFIGURATION
# ============================================================

DATA_PATH = "data/raw/Weather_Forecasting.csv"
MODEL_PATH = "models/gru.keras"

TIME_STEPS = 24
FORECAST_HOURS = 24

CITIES = {
    "Delhi": {
        "latitude": 28.6139,
        "longitude": 77.2090
    },
    "Mumbai": {
        "latitude": 19.0760,
        "longitude": 72.8777
    },
    "Bengaluru": {
        "latitude": 12.9716,
        "longitude": 77.5946
    },
    "Chennai": {
        "latitude": 13.0827,
        "longitude": 80.2707
    },
    "Bhopal": {
        "latitude": 23.2599,
        "longitude": 77.4126
    }
}


# ============================================================
# LOAD DATA AND MODEL
# ============================================================

df = pd.read_csv(DATA_PATH)

gru_model = load_model(MODEL_PATH)


# ============================================================
# GET HOURLY WEATHER FORECAST
# ============================================================

def get_hourly_forecast(latitude, longitude):

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,

        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "dew_point_2m",
            "apparent_temperature",
            "precipitation",
            "rain",
            "surface_pressure",
            "cloud_cover",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m"
        ]),

        "forecast_days": 2,
        "timezone": "Asia/Kolkata"
    }

    response = requests.get(
        url,
        params=params,
        timeout=20
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# CONVERT OPEN-METEO RESPONSE TO DATAFRAME
# ============================================================

def forecast_to_dataframe(weather_data):

    hourly = weather_data["hourly"]

    future_df = pd.DataFrame({
        "time": hourly["time"],
        "temperature_2m": hourly["temperature_2m"],
        "relative_humidity_2m": hourly["relative_humidity_2m"],
        "dew_point_2m": hourly["dew_point_2m"],
        "apparent_temperature": hourly["apparent_temperature"],
        "precipitation": hourly["precipitation"],
        "rain": hourly["rain"],
        "surface_pressure": hourly["surface_pressure"],
        "cloud_cover": hourly["cloud_cover"],
        "wind_speed_10m": hourly["wind_speed_10m"],
        "wind_direction_10m": hourly["wind_direction_10m"],
        "wind_gusts_10m": hourly["wind_gusts_10m"]
    })

    return future_df


# ============================================================
# PREDICT NEXT HOUR
# ============================================================

def predict_next_hour(history_df):

    # Create the exact same features used during training
    featured_df = create_features(history_df)

    # Remove rows where lag/rolling features are incomplete
    featured_df = featured_df.dropna(
        subset=FEATURE_COLUMNS
    ).copy()

    # We need the latest 24 rows
    latest_24 = featured_df.tail(TIME_STEPS)

    if len(latest_24) != TIME_STEPS:
        raise ValueError(
            "Could not create 24 complete rows for GRU input."
        )

    # Select the exact 25 training features
    X = latest_24[FEATURE_COLUMNS]

    # Scale using the original training scaler
    X_scaled = scaler.transform(X)

    # Shape:
    # (24, 25) -> (1, 24, 25)
    X_sequence = X_scaled.reshape(
        1,
        TIME_STEPS,
        len(FEATURE_COLUMNS)
    )

    # GRU prediction
    prediction = gru_model.predict(
        X_sequence,
        verbose=0
    )[0][0]

    return float(prediction)


# ============================================================
# FORECAST ONE CITY
# ============================================================

def forecast_city(city):

    print("\n")
    print("=" * 70)
    print(f"{city.upper()} - 4 HOUR GRU FORECAST")
    print("=" * 70)

    # Historical data for this city
    city_history = df[
        df["city"] == city
    ].copy()

    city_history["time"] = pd.to_datetime(
        city_history["time"]
    )

    city_history = city_history.sort_values(
        "time"
    ).reset_index(drop=True)

    print(
        "Historical rows:",
        len(city_history)
    )

    print(
        "Last historical time:",
        city_history["time"].iloc[-1]
    )

    print(
        "Last historical temperature:",
        city_history["temperature_2m"].iloc[-1],
        "°C"
    )

    # --------------------------------------------------------
    # Get Open-Meteo hourly forecast
    # --------------------------------------------------------

    coordinates = CITIES[city]

    weather_data = get_hourly_forecast(
        coordinates["latitude"],
        coordinates["longitude"]
    )

    forecast_df = forecast_to_dataframe(
        weather_data
    )

    forecast_df["time"] = pd.to_datetime(
        forecast_df["time"]
    )

    # --------------------------------------------------------
    # Only use forecast hours AFTER historical data
    # --------------------------------------------------------

    last_historical_time = city_history["time"].iloc[-1]

    future_weather = forecast_df[
        forecast_df["time"] > last_historical_time
    ].copy()

    future_weather = future_weather.head(
        FORECAST_HOURS
    ).reset_index(drop=True)

    if len(future_weather) < FORECAST_HOURS:

        raise ValueError(
            f"Open-Meteo returned only "
            f"{len(future_weather)} future hours "
            f"for {city}."
        )

    print(
        "\nForecast hours obtained:",
        len(future_weather)
    )

    # --------------------------------------------------------
    # History used for recursive forecasting
    # --------------------------------------------------------

    working_df = city_history.copy()

    predictions = []

    # --------------------------------------------------------
    # Recursive 4-hour forecasting
    # --------------------------------------------------------

    for i in range(FORECAST_HOURS):

        future_row = future_weather.iloc[i]

        future_time = future_row["time"]

        print(
            f"\nPredicting hour {i + 1}:",
            future_time
        )

        # ----------------------------------------------------
        # Predict next hour using the previous 24 rows
        # ----------------------------------------------------

        prediction = predict_next_hour(
            working_df
        )

        print(
            "Predicted temperature:",
            round(prediction, 2),
            "°C"
        )

        # ----------------------------------------------------
        # Save prediction
        # ----------------------------------------------------

        predictions.append({
            "city": city,
            "time": str(future_time),
            "predicted_temperature": round(
                prediction,
                2
            )
        })

        # ----------------------------------------------------
        # Add predicted temperature to the future row
        #
        # This predicted value becomes historical input
        # for the next recursive prediction.
        # ----------------------------------------------------

        new_row = {
            "time": future_time,
            "temperature_2m": prediction,
            "relative_humidity_2m":
                future_row["relative_humidity_2m"],
            "dew_point_2m":
                future_row["dew_point_2m"],
            "apparent_temperature":
                future_row["apparent_temperature"],
            "precipitation":
                future_row["precipitation"],
            "rain":
                future_row["rain"],
            "surface_pressure":
                future_row["surface_pressure"],
            "cloud_cover":
                future_row["cloud_cover"],
            "wind_speed_10m":
                future_row["wind_speed_10m"],
            "wind_direction_10m":
                future_row["wind_direction_10m"],
            "wind_gusts_10m":
                future_row["wind_gusts_10m"],
            "city": city
        }

        # Add the new predicted hour
        working_df = pd.concat(
            [
                working_df,
                pd.DataFrame([new_row])
            ],
            ignore_index=True
        )

    # --------------------------------------------------------
    # Display city results
    # --------------------------------------------------------

    result_df = pd.DataFrame(
        predictions
    )

    print("\n")
    print("-" * 70)
    print(f"{city} - FORECAST RESULT")
    print("-" * 70)

    print(
        result_df.to_string(
            index=False
        )
    )

    return predictions


# ============================================================
# RUN ALL 5 CITIES
# ============================================================

all_results = []

for city in CITIES:

    try:

        city_results = forecast_city(
            city
        )

        all_results.extend(
            city_results
        )

    except Exception as e:

        print("\n")
        print(
            f"ERROR while forecasting {city}:"
        )

        print(e)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n")
print("=" * 70)
print("ALL 5 CITIES - 4 HOUR GRU FORECAST")
print("=" * 70)

final_df = pd.DataFrame(
    all_results
)

if not final_df.empty:

    print(
        final_df.to_string(
            index=False
        )
    )

print("=" * 70)
print("ALL 5 CITIES - 24 HOUR GRU FORECAST")
print("=" * 70)

final_df = pd.DataFrame(all_results)

if not final_df.empty:
    print(
        final_df.to_string(index=False)
    )

print("=" * 70)
print("24-HOUR FORECAST TEST COMPLETED")
print("=" * 70)