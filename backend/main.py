from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import requests

from fastapi import FastAPI, HTTPException
from tensorflow.keras.models import load_model

from backend.live_weather import CITIES, get_latest_hourly_weather
from backend.feature_engineering import create_features, FEATURE_COLUMNS
from backend.model_loader import xgb_model, scaler
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data" / "raw"

CSV_PATH = DATA_DIR / "Weather_Forecasting.csv"

XGB_MODEL_PATH = MODEL_DIR / "xgboost.pkl"
SCALER_PATH = MODEL_DIR / "scaler.pkl"
GRU_MODEL_PATH = MODEL_DIR / "gru.keras"


# ============================================================
# LOAD MODELS
# ============================================================

print("Loading models...")

xgb_model = joblib.load(XGB_MODEL_PATH)

# Scaler is used for GRU / sequence models.
scaler = joblib.load(SCALER_PATH)

gru_model = load_model(GRU_MODEL_PATH)

print("XGBoost model loaded successfully.")
print("Scaler loaded successfully.")
print("GRU model loaded successfully.")


# ============================================================
# LOAD HISTORICAL DATA
# ============================================================

print("Loading historical dataset...")

historical_df = pd.read_csv(CSV_PATH)

historical_df["time"] = pd.to_datetime(
    historical_df["time"],
    format="mixed"
)

historical_df = historical_df.sort_values(
    ["city", "time"]
).reset_index(drop=True)

print("Historical dataset loaded.")
print("Rows:", len(historical_df))


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Weather Forecasting AI",
    description="AI-powered weather forecasting using XGBoost and GRU.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def normalize_city(city: str) -> str:
    city = city.strip().lower()

    city_map = {
        "delhi": "Delhi",
        "mumbai": "Mumbai",
        "bengaluru": "Bengaluru",
        "chennai": "Chennai",
        "bhopal": "Bhopal"
    }

    if city not in city_map:
        raise HTTPException(
            status_code=404,
            detail=f"City '{city}' is not supported."
        )

    return city_map[city]
# ============================================================
# COMBINE HISTORICAL + LATEST WEATHER DATA
# ============================================================

def get_combined_weather_data(city: str):

    city = normalize_city(city)

    if city not in CITIES:
        raise HTTPException(
            status_code=404,
            detail=f"City '{city}' is not supported."
        )

    city_info = CITIES[city]

    # --------------------------------------------------------
    # Historical data
    # --------------------------------------------------------

    city_history = historical_df[
        historical_df["city"] == city
    ].copy()

    if city_history.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No historical data found for {city}."
        )

    # --------------------------------------------------------
    # Latest hourly weather from Open-Meteo
    # --------------------------------------------------------

    try:

        live_data = get_latest_hourly_weather(
            city_info["latitude"],
            city_info["longitude"]
        )

    except requests.RequestException as e:

        raise HTTPException(
            status_code=503,
            detail=f"Unable to retrieve live weather data: {str(e)}"
        )

    hourly = live_data.get("hourly")

    if hourly is None:
        raise HTTPException(
            status_code=503,
            detail="Hourly weather data was not returned by the weather API."
        )

    live_df = pd.DataFrame(hourly)

    # Add city information
    live_df["city"] = city
    live_df["state"] = city_info.get("state", "")
    live_df["latitude"] = city_info["latitude"]
    live_df["longitude"] = city_info["longitude"]

    live_df["time"] = pd.to_datetime(
        live_df["time"],
        format="mixed"
    )

    # --------------------------------------------------------
    # Combine
    # --------------------------------------------------------

    combined_df = pd.concat(
        [city_history, live_df],
        ignore_index=True
    )

    # If the live API contains timestamps that already exist
    # in historical data, keep the latest API observation.
    combined_df = (
        combined_df
        .drop_duplicates(
            subset=["city", "time"],
            keep="last"
        )
        .sort_values("time")
        .reset_index(drop=True)
    )

    return combined_df


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "message": "Weather Forecasting AI API is running.",
        "models": [
            "XGBoost - next hour",
            "GRU - sequence forecasting"
        ],
        "cities": list(CITIES.keys())
    }


# ============================================================
# CITIES
# ============================================================

@app.get("/cities")
def get_cities():

    return {
        "cities": list(CITIES.keys())
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "xgboost_loaded": xgb_model is not None,
        "scaler_loaded": scaler is not None,
        "gru_loaded": gru_model is not None,
        "historical_rows": len(historical_df)
    }


# ============================================================
# NEXT-HOUR XGBOOST PREDICTION
# ============================================================

@app.get("/predict/{city}")
def predict_next_hour(city: str):

    city = normalize_city(city)

    # --------------------------------------------------------
    # Get historical + latest weather data
    # --------------------------------------------------------

    combined_df = get_combined_weather_data(city)

    # --------------------------------------------------------
    # Create the same 25 features used during training
    # --------------------------------------------------------

    featured_df = create_features(combined_df)

    # Remove rows where lag/rolling features cannot exist
    featured_df = featured_df.dropna(
        subset=FEATURE_COLUMNS
    ).reset_index(drop=True)

    if featured_df.empty:
        raise HTTPException(
            status_code=500,
            detail="Unable to create prediction features."
        )

    # --------------------------------------------------------
    # IMPORTANT:
    # Select the latest time that is NOT in the future.
    #
    # The live Open-Meteo data may contain future hourly
    # forecast records. Therefore, we must NOT simply use:
    #
    # featured_df.iloc[-1]
    # --------------------------------------------------------

    current_time = pd.Timestamp.now(
        tz="Asia/Kolkata"
    ).tz_localize(None)

    # Make sure time column is datetime
    featured_df["time"] = pd.to_datetime(
        featured_df["time"]
    )

    # Remove future records
    available_df = featured_df[
        featured_df["time"] <= current_time
    ].copy()

    if available_df.empty:
        raise HTTPException(
            status_code=500,
            detail="No weather data available up to the current time."
        )

    # --------------------------------------------------------
    # Latest actual/current available observation
    # --------------------------------------------------------

    latest_row = available_df.iloc[-1]

    latest_time = pd.Timestamp(
        latest_row["time"]
    )

    latest_features = latest_row[
        FEATURE_COLUMNS
    ].to_numpy(
        dtype=float
    ).reshape(1, -1)

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # XGBoost was trained using RAW X_train.
    #
    # Therefore DO NOT use:
    #
    # scaler.transform(latest_features)
    #
    # here.
    # --------------------------------------------------------

    prediction = xgb_model.predict(
        latest_features
    )

    predicted_temperature = float(
        prediction[0]
    )

    # --------------------------------------------------------
    # Next hour
    # --------------------------------------------------------

    prediction_time = (
        latest_time
        + pd.Timedelta(hours=1)
    )

    # --------------------------------------------------------
    # Return result
    # --------------------------------------------------------

    return {
        "city": city,

        "latest_data_time": str(
            latest_time
        ),

        "latest_temperature": round(
            float(
                latest_row["temperature_2m"]
            ),
            2
        ),

        "prediction_time": str(
            prediction_time
        ),

        "predicted_temperature": round(
            predicted_temperature,
            2
        ),

        "model": "XGBoost",

        "features": len(
            FEATURE_COLUMNS
        )
    }


# ============================================================
# 24-HOUR GRU FORECAST
# ============================================================

TIME_STEPS = 24
@app.get("/predict/tomorrow/{city}")
def predict_next_24_hours(city: str):

    # --------------------------------------------------------
    # Validate city
    # --------------------------------------------------------

    city = normalize_city(city)

    # --------------------------------------------------------
    # Get historical + latest weather data
    # --------------------------------------------------------

    combined_df = get_combined_weather_data(city)

    # --------------------------------------------------------
    # Create the same 25 features used during training
    # --------------------------------------------------------

    featured_df = create_features(combined_df)

    featured_df = featured_df.dropna(
        subset=FEATURE_COLUMNS
    ).reset_index(drop=True)

    if len(featured_df) < TIME_STEPS:
        raise HTTPException(
            status_code=500,
            detail="Not enough data to create a 24-hour GRU forecast."
        )

    # --------------------------------------------------------
    # Take the latest 24 observations
    # --------------------------------------------------------

    latest_sequence = featured_df[
        FEATURE_COLUMNS
    ].tail(TIME_STEPS).to_numpy(
        dtype=float
    )

    # --------------------------------------------------------
    # Scale features
    #
    # GRU was trained using scaled features.
    # --------------------------------------------------------

    scaled_sequence = scaler.transform(
        latest_sequence
    )

    # Shape:
    # (1, 24, 25)
    current_sequence = scaled_sequence.reshape(
        1,
        TIME_STEPS,
        len(FEATURE_COLUMNS)
    )

    # --------------------------------------------------------
    # Starting timestamp
    # --------------------------------------------------------

    last_time = pd.Timestamp(
        featured_df.iloc[-1]["time"]
    )

    # --------------------------------------------------------
    # Recursive 24-hour forecasting
    # --------------------------------------------------------

    predictions = []

    for step in range(1, 25):

        # Predict next temperature
        prediction = gru_model.predict(
            current_sequence,
            verbose=0
        )

        predicted_temperature = float(
            prediction[0][0]
        )

        # Forecast timestamp
        forecast_time = (
            last_time
            + pd.Timedelta(hours=step)
        )

        predictions.append(
            {
                "time": str(forecast_time),
                "predicted_temperature": round(
                    predicted_temperature,
                    2
                )
            }
        )

        # ----------------------------------------------------
        # Recursive update
        #
        # The predicted temperature becomes the temperature
        # used in the next sequence.
        #
        # Other feature values are kept from the latest
        # available observation.
        # ----------------------------------------------------

        next_row = current_sequence[0, -1, :].copy()

        # Find scaled temperature feature
        temperature_index = FEATURE_COLUMNS.index(
            "temperature_2m"
        )

        # Scale predicted temperature using the same scaler
        temperature_mean = scaler.mean_[temperature_index]
        temperature_scale = scaler.scale_[temperature_index]

        scaled_predicted_temperature = (
            predicted_temperature - temperature_mean
        ) / temperature_scale

        next_row[temperature_index] = (
            scaled_predicted_temperature
        )

        # Shift the sequence forward by one hour
        current_sequence = np.concatenate(
            [
                current_sequence[:, 1:, :],
                next_row.reshape(1, 1, -1)
            ],
            axis=1
        )

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {
        "city": city,
        "model": "GRU",
        "forecast_hours": 24,
        "features": len(FEATURE_COLUMNS),
        "time_steps": TIME_STEPS,
        "last_data_time": str(last_time),
        "predictions": predictions
    }
# ============================================================
# 10-DAY GRU FORECAST USING OPEN-METEO FUTURE WEATHER DATA
# ============================================================

def get_10_day_weather_data(city: str):

    # --------------------------------------------------------
    # Validate city
    # --------------------------------------------------------

    if city not in CITIES:
        raise HTTPException(
            status_code=404,
            detail=f"City '{city}' is not supported."
        )

    city_info = CITIES[city]

    # --------------------------------------------------------
    # Get Open-Meteo hourly data
    # --------------------------------------------------------

    try:
        weather_data = get_latest_hourly_weather(
            city_info["latitude"],
            city_info["longitude"]
        )
    except requests.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Unable to retrieve Open-Meteo data: {str(e)}"
        )

    # --------------------------------------------------------
    # Check API response
    # --------------------------------------------------------

    if "hourly" not in weather_data:
        raise HTTPException(
            status_code=503,
            detail="Open-Meteo did not return hourly weather data."
        )

    hourly = weather_data["hourly"]

    required_columns = [
        "time",
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
    ]

    # --------------------------------------------------------
    # Check required API columns
    # --------------------------------------------------------

    missing_columns = [
        column
        for column in required_columns
        if column not in hourly
    ]

    if missing_columns:
        raise HTTPException(
            status_code=503,
            detail=f"Missing Open-Meteo columns: {missing_columns}"
        )

    # --------------------------------------------------------
    # Create API DataFrame
    # --------------------------------------------------------

    api_df = pd.DataFrame({
        column: hourly[column]
        for column in required_columns
    })

    api_df["time"] = pd.to_datetime(
        api_df["time"],
        format="mixed"
    )

    api_df["city"] = city

    # --------------------------------------------------------
    # Historical data for selected city
    # --------------------------------------------------------

    historical_city_df = historical_df[
        historical_df["city"] == city
    ].copy()

    if historical_city_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No historical data found for {city}."
        )

    historical_columns = [
        "time",
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
        "wind_gusts_10m",
        "city"
    ]

    historical_city_df = historical_city_df[
        historical_columns
    ].copy()

    historical_city_df["time"] = pd.to_datetime(
        historical_city_df["time"],
        format="mixed"
    )

    # --------------------------------------------------------
    # Find last historical observation
    # --------------------------------------------------------

    last_historical_time = (
        historical_city_df["time"].max()
    )

    # --------------------------------------------------------
    # Only take API rows after historical data
    # --------------------------------------------------------

    new_api_data = api_df[
        api_df["time"] > last_historical_time
    ].copy()

    new_api_data = (
        new_api_data
        .sort_values("time")
        .drop_duplicates(
            subset=["city", "time"],
            keep="last"
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # We need:
    #
    # 24 hours of context
    # +
    # 240 future hours
    #
    # Total = 264 hours
    # --------------------------------------------------------

    if len(new_api_data) < 264:
        raise HTTPException(
            status_code=503,
            detail=(
                "Open-Meteo returned insufficient hourly data. "
                f"Expected at least 264 rows, got {len(new_api_data)}."
            )
        )

    # --------------------------------------------------------
    # First 24 rows = current/context data
    # Remaining 240 = future forecast
    # --------------------------------------------------------

    current_context = new_api_data.iloc[:24].copy()

    future_forecast = (
        new_api_data
        .iloc[24:264]
        .copy()
        .reset_index(drop=True)
    )

    if len(future_forecast) != 240:
        raise HTTPException(
            status_code=503,
            detail=(
                "Unable to obtain exactly 240 future forecast hours. "
                f"Got {len(future_forecast)} hours."
            )
        )

    # --------------------------------------------------------
    # Historical + current Open-Meteo context
    # --------------------------------------------------------

    model_history = pd.concat(
        [
            historical_city_df,
            current_context
        ],
        ignore_index=True
    )

    model_history = (
        model_history
        .drop_duplicates(
            subset=["city", "time"],
            keep="last"
        )
        .sort_values("time")
        .reset_index(drop=True)
    )

    return model_history, future_forecast


# ============================================================
# 10-DAY FORECAST ENDPOINT
# ============================================================

@app.get("/predict/10days/{city}")
def predict_next_10_days(city: str):

    city = normalize_city(city)

    try:
        return predict_next_10_days_internal(city)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"10-day forecast failed: {type(e).__name__}: {str(e)}"
        )
def predict_next_10_days_internal(city: str):
    # --------------------------------------------------------
    # Get historical + current context
    # and future Open-Meteo data
    # --------------------------------------------------------

    model_history, future_forecast = (
        get_10_day_weather_data(city)
    )

    working_df = model_history.copy()

    predictions = []

    # --------------------------------------------------------
    # Generate 240 hourly predictions
    # --------------------------------------------------------

    for step in range(240):

        # ----------------------------------------------------
        # Create the same features used during training
        # ----------------------------------------------------

        featured_df = create_features(
            working_df
        )

        featured_df = (
            featured_df
            .dropna(subset=FEATURE_COLUMNS)
            .reset_index(drop=True)
        )

        if len(featured_df) < TIME_STEPS:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Not enough feature rows to create "
                    "the GRU sequence."
                )
            )

        # ----------------------------------------------------
        # Take latest 24 hours
        # ----------------------------------------------------

        latest_sequence = (
            featured_df[
                FEATURE_COLUMNS
            ]
            .tail(TIME_STEPS)
            .to_numpy(dtype=float)
        )

        # ----------------------------------------------------
        # Check for invalid values
        # ----------------------------------------------------

        if not np.isfinite(latest_sequence).all():
            raise HTTPException(
                status_code=500,
                detail=(
                    "Invalid numerical values found "
                    "in GRU input features."
                )
            )

        # ----------------------------------------------------
        # Scale using training scaler
        # ----------------------------------------------------

        scaled_sequence = scaler.transform(
            latest_sequence
        )

        current_sequence = scaled_sequence.reshape(
            1,
            TIME_STEPS,
            len(FEATURE_COLUMNS)
        )

        # ----------------------------------------------------
        # GRU prediction
        # ----------------------------------------------------

        prediction = gru_model.predict(
            current_sequence,
            verbose=0
        )

        predicted_temperature = float(
            prediction[0][0]
        )

        # ----------------------------------------------------
        # Corresponding Open-Meteo future row
        # ----------------------------------------------------

        future_row = (
            future_forecast
            .iloc[step]
            .copy()
        )

        forecast_time = pd.Timestamp(
            future_row["time"]
        )

        # ----------------------------------------------------
        # Save prediction
        # ----------------------------------------------------

        predictions.append({
            "time": str(forecast_time),
            "predicted_temperature": round(
                predicted_temperature,
                2
            )
        })

        # ----------------------------------------------------
        # Add Open-Meteo future weather data
        # to the working history.
        #
        # This allows lag and rolling features
        # to update at every hour.
        # ----------------------------------------------------

        new_row = future_row.to_dict()

        working_df = pd.concat(
            [
                working_df,
                pd.DataFrame([new_row])
            ],
            ignore_index=True
        )

    # ========================================================
    # Convert hourly predictions into daily forecasts
    # ========================================================

    prediction_df = pd.DataFrame(
        predictions
    )

    prediction_df["time"] = pd.to_datetime(
        prediction_df["time"]
    )

    prediction_df["date"] = (
        prediction_df["time"]
        .dt.date
    )

    daily_forecast = []

    for day_number, (date, group) in enumerate(
        prediction_df.groupby("date"),
        start=1
    ):

        daily_forecast.append({
            "day": day_number,
            "date": str(date),
            "min_temperature": round(
                float(
                    group[
                        "predicted_temperature"
                    ].min()
                ),
                2
            ),
            "max_temperature": round(
                float(
                    group[
                        "predicted_temperature"
                    ].max()
                ),
                2
            ),
            "avg_temperature": round(
                float(
                    group[
                        "predicted_temperature"
                    ].mean()
                ),
                2
            )
        })

    # ========================================================
    # Final response
    # ========================================================

    return {
        "city": city,
        "model": "GRU",
        "forecast_days": len(daily_forecast),
        "forecast_hours": len(predictions),
        "time_steps": TIME_STEPS,
        "last_data_time": str(
            model_history.iloc[-1]["time"]
        ),
        "daily_forecast": daily_forecast
    }