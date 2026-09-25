import pandas as pd

from backend.live_weather import CITIES, get_live_weather
from backend.feature_engineering import create_features, FEATURE_COLUMNS
from backend.model_loader import xgb_model


DATA_PATH = "data/raw/Weather_Forecasting.csv"


def predict_live_temperature(city):
    print("\n" + "=" * 60)
    print(f"LIVE XGBOOST PREDICTION: {city}")
    print("=" * 60)

    # 1. Load historical data
    df = pd.read_csv(DATA_PATH)

    # Keep only the selected city
    city_df = df[df["city"] == city].copy()

    # 2. Get live weather
    coordinates = CITIES[city]

    live_weather = get_live_weather(
        coordinates["latitude"],
        coordinates["longitude"]
    )

    current = live_weather["current"]

    # 3. Create live weather row
    live_row = {
        "time": current["time"],
        "temperature_2m": current["temperature_2m"],
        "relative_humidity_2m": current["relative_humidity_2m"],
        "dew_point_2m": current["dew_point_2m"],
        "apparent_temperature": current["apparent_temperature"],
        "precipitation": current["precipitation"],
        "rain": current["rain"],
        "surface_pressure": current["surface_pressure"],
        "cloud_cover": current["cloud_cover"],
        "wind_speed_10m": current["wind_speed_10m"],
        "wind_direction_10m": current["wind_direction_10m"],
        "wind_gusts_10m": current["wind_gusts_10m"],
        "city": city,
    }

    live_df = pd.DataFrame([live_row])

    # 4. Combine historical + live data
    combined_df = pd.concat(
        [city_df, live_df],
        ignore_index=True
    )

    # 5. Generate the 25 model features
    featured_df = create_features(combined_df)

    # 6. Get the live row
    latest_row = featured_df.tail(1)

    # 7. Check for missing features
    if latest_row[FEATURE_COLUMNS].isnull().any().any():
        print("ERROR: Missing feature values.")
        return

    # 8. Prepare input for XGBoost
    X_live = latest_row[FEATURE_COLUMNS].values

    # 9. Make prediction
    prediction = xgb_model.predict(X_live)[0]

    # 10. Display result
    print("Live observation time:", latest_row["time"].iloc[0])
    print("Current temperature:", current["temperature_2m"], "°C")
    print("Predicted next-hour temperature:", round(float(prediction), 2), "°C")


if __name__ == "__main__":

    for city in CITIES:
        try:
            predict_live_temperature(city)

        except Exception as e:
            print(f"\nERROR for {city}: {e}")