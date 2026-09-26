from pathlib import Path
import sqlite3

import joblib
import numpy as np
import pandas as pd
import requests

from fastapi import Depends, FastAPI, HTTPException, status
from tensorflow.keras.models import load_model

from fastapi.middleware.cors import CORSMiddleware

from backend.cities import CITIES
from backend.live_weather import get_latest_hourly_weather
from backend.feature_engineering import create_features, FEATURE_COLUMNS
from backend.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password
)
from backend.config import get_cors_origins
from backend.database import (
    create_user,
    get_user_by_email,
    initialize_database
)
from backend.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data" / "raw"

CSV_PATH = DATA_DIR / "Weather_Forecasting_final.csv"

XGB_MODEL_PATH = MODEL_DIR / "xgboost.pkl"
SCALER_PATH = MODEL_DIR / "scaler.pkl"
GRU_MODEL_PATH = MODEL_DIR / "gru.keras"


# ============================================================
# LOAD MODELS
# ============================================================

print("Loading models...")

xgb_model = joblib.load(XGB_MODEL_PATH)

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

historical_df = (
    historical_df
    .sort_values(["city", "time"])
    .reset_index(drop=True)
)

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
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

initialize_database()


# ============================================================
# AUTHENTICATION
# ============================================================

@app.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED
)
def register_user(payload: RegisterRequest):

    """Create an account and return an access token."""

    email = payload.email.strip().lower()

    if get_user_by_email(email):

        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists."
        )

    try:

        user = create_user(
            email,
            hash_password(payload.password)
        )

    except sqlite3.IntegrityError as error:

        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists."
        ) from error

    return {
        "access_token": create_access_token(user["email"]),
        "user": user
    }


@app.post(
    "/auth/login",
    response_model=TokenResponse
)
def login_user(payload: LoginRequest):

    """Verify credentials and issue a JWT."""

    email = payload.email.strip().lower()

    user = get_user_by_email(email)

    if not user or not verify_password(
        payload.password,
        user["password_hash"]
    ):

        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password."
        )

    return {
        "access_token": create_access_token(user["email"]),
        "user": user
    }


@app.get(
    "/auth/me",
    response_model=UserResponse
)
def get_me(
    current_user: dict = Depends(get_current_user)
):

    return current_user


# ============================================================
# CITY NORMALIZATION
# ============================================================

def normalize_city(city: str) -> str:

    """
    Normalize user-provided city name and validate
    it against the central CITIES dictionary.
    """

    city = city.strip()

    aliases = {
        "new delhi": "Delhi",
        "delhi": "Delhi"
    }

    if city.lower() in aliases:

        return aliases[city.lower()]

    for supported_city in CITIES.keys():

        if city.lower() == supported_city.lower():

            return supported_city

    raise HTTPException(
        status_code=404,
        detail=f"City '{city}' is not supported."
    )


# ============================================================
# CONSTANTS
# ============================================================

TIME_STEPS = 24


# ============================================================
# COMBINE HISTORICAL + LIVE WEATHER DATA
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
    # Live Open-Meteo hourly data
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
            detail=(
                "Hourly weather data was not returned "
                "by the weather API."
            )
        )

    live_df = pd.DataFrame(hourly)

    live_df["city"] = city

    live_df["state"] = city_info.get(
        "state",
        ""
    )

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
        [
            city_history,
            live_df
        ],
        ignore_index=True
    )

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
def get_cities(
    current_user: dict = Depends(get_current_user)
):

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
def predict_next_hour(
    city: str,
    current_user: dict = Depends(get_current_user)
):

    city = normalize_city(city)

    # --------------------------------------------------------
    # Get historical + live weather data
    # --------------------------------------------------------

    combined_df = get_combined_weather_data(city)

    # --------------------------------------------------------
    # IMPORTANT:
    # Remove future Open-Meteo forecast rows BEFORE
    # creating features.
    # --------------------------------------------------------

    current_time = pd.Timestamp.now(
        tz="Asia/Kolkata"
    ).tz_localize(None)

    combined_df["time"] = pd.to_datetime(
        combined_df["time"],
        format="mixed"
    )

    available_weather = combined_df[
        combined_df["time"] <= current_time
    ].copy()

    if available_weather.empty:

        raise HTTPException(
            status_code=500,
            detail="No weather data available up to the current time."
        )

    # --------------------------------------------------------
    # Create 25 features
    # --------------------------------------------------------

    featured_df = create_features(
        available_weather
    )

    featured_df = (
        featured_df
        .dropna(subset=FEATURE_COLUMNS)
        .reset_index(drop=True)
    )

    if featured_df.empty:

        raise HTTPException(
            status_code=500,
            detail="Unable to create prediction features."
        )

    # --------------------------------------------------------
    # Latest actual available observation
    # --------------------------------------------------------

    latest_row = featured_df.iloc[-1]

    latest_time = pd.Timestamp(
        latest_row["time"]
    )

    latest_features = (
        latest_row[
            FEATURE_COLUMNS
        ]
        .to_numpy(dtype=float)
        .reshape(1, -1)
    )

    # --------------------------------------------------------
    # XGBoost uses RAW features
    # --------------------------------------------------------

    prediction = xgb_model.predict(
        latest_features
    )

    predicted_temperature = float(
        prediction[0]
    )

    prediction_time = (
        latest_time
        + pd.Timedelta(hours=1)
    )

    # --------------------------------------------------------
    # Response
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
# 24-HOUR GRU FORECAST USING LIVE DATA
# ============================================================

@app.get("/predict/tomorrow/{city}")
def predict_next_24_hours(
    city: str,
    current_user: dict = Depends(get_current_user)
):

    # --------------------------------------------------------
    # Validate city
    # --------------------------------------------------------

    city = normalize_city(city)

    city_info = CITIES[city]

    # --------------------------------------------------------
    # Get live Open-Meteo hourly data
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

    if "hourly" not in live_data:

        raise HTTPException(
            status_code=503,
            detail="Hourly weather data was not returned by Open-Meteo."
        )

    # --------------------------------------------------------
    # Convert API response to DataFrame
    # --------------------------------------------------------

    live_df = pd.DataFrame(
        live_data["hourly"]
    )

    live_df["time"] = pd.to_datetime(
        live_df["time"],
        format="mixed"
    )

    live_df["city"] = city

    live_df["state"] = city_info["state"]

    live_df["latitude"] = city_info["latitude"]

    live_df["longitude"] = city_info["longitude"]

    # --------------------------------------------------------
    # Current time
    # --------------------------------------------------------

    current_time = pd.Timestamp.now(
        tz="Asia/Kolkata"
    ).tz_localize(None)

    # --------------------------------------------------------
    # Past/current live observations
    # --------------------------------------------------------

    past_live = (
        live_df[
            live_df["time"] <= current_time
        ]
        .sort_values("time")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Future live forecast
    # --------------------------------------------------------

    future_live = (
        live_df[
            live_df["time"] > current_time
        ]
        .sort_values("time")
        .reset_index(drop=True)
    )

    if past_live.empty:

        raise HTTPException(
            status_code=503,
            detail="No current live weather observation is available."
        )

    if len(future_live) < 24:

        raise HTTPException(
            status_code=503,
            detail="Open-Meteo returned fewer than 24 future hours."
        )

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
    # Historical + live past/current data
    # --------------------------------------------------------

    context_df = pd.concat(
        [
            city_history,
            past_live
        ],
        ignore_index=True
    )

    context_df = (
        context_df
        .drop_duplicates(
            subset=["city", "time"],
            keep="last"
        )
        .sort_values("time")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Create 25 features
    # --------------------------------------------------------

    featured_df = create_features(
        context_df
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
                "Not enough data to create "
                "a 24-hour GRU forecast."
            )
        )

    # --------------------------------------------------------
    # Latest 24-hour sequence
    # --------------------------------------------------------

    latest_sequence = (
        featured_df[
            FEATURE_COLUMNS
        ]
        .tail(TIME_STEPS)
        .to_numpy(dtype=float)
    )

    if not np.isfinite(
        latest_sequence
    ).all():

        raise HTTPException(
            status_code=500,
            detail="Invalid numerical values found in GRU input."
        )

    # --------------------------------------------------------
    # Scale
    # --------------------------------------------------------

    scaled_sequence = scaler.transform(
        latest_sequence
    )

    current_sequence = scaled_sequence.reshape(
        1,
        TIME_STEPS,
        len(FEATURE_COLUMNS)
    )

    # --------------------------------------------------------
    # Latest LIVE timestamp
    # --------------------------------------------------------

    latest_live_time = pd.Timestamp(
        past_live.iloc[-1]["time"]
    )

    # --------------------------------------------------------
    # Recursive 24-hour prediction
    # --------------------------------------------------------

    predictions = []

    temperature_index = FEATURE_COLUMNS.index(
        "temperature_2m"
    )

    for step in range(24):

        prediction = gru_model.predict(
            current_sequence,
            verbose=0
        )

        predicted_temperature = float(
            prediction[0][0]
        )

        forecast_time = pd.Timestamp(
            future_live.iloc[step]["time"]
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
        # Recursive temperature update
        # ----------------------------------------------------

        next_row = current_sequence[
            0,
            -1,
            :
        ].copy()

        temperature_mean = scaler.mean_[
            temperature_index
        ]

        temperature_scale = scaler.scale_[
            temperature_index
        ]

        scaled_predicted_temperature = (
            predicted_temperature
            - temperature_mean
        ) / temperature_scale

        next_row[
            temperature_index
        ] = scaled_predicted_temperature

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

        "features": len(
            FEATURE_COLUMNS
        ),

        "time_steps": TIME_STEPS,

        "last_data_time": str(
            latest_live_time
        ),

        "predictions": predictions
    }


# ============================================================
# 10-DAY GRU FORECAST DATA
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

    if "hourly" not in weather_data:

        raise HTTPException(
            status_code=503,
            detail="Open-Meteo did not return hourly weather data."
        )

    hourly = weather_data["hourly"]

    # --------------------------------------------------------
    # Required columns
    # --------------------------------------------------------

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

    missing_columns = [
        column
        for column in required_columns
        if column not in hourly
    ]

    if missing_columns:

        raise HTTPException(
            status_code=503,
            detail=(
                f"Missing Open-Meteo columns: "
                f"{missing_columns}"
            )
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

    api_df["state"] = city_info["state"]

    api_df["latitude"] = city_info["latitude"]

    api_df["longitude"] = city_info["longitude"]

    # --------------------------------------------------------
    # Current time
    # --------------------------------------------------------

    current_time = pd.Timestamp.now(
        tz="Asia/Kolkata"
    ).tz_localize(None)

    # --------------------------------------------------------
    # LIVE PAST / CURRENT DATA
    # --------------------------------------------------------

    past_live = (
        api_df[
            api_df["time"] <= current_time
        ]
        .sort_values("time")
        .drop_duplicates(
            subset=["city", "time"],
            keep="last"
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # LIVE FUTURE DATA
    # --------------------------------------------------------

    future_live = (
        api_df[
            api_df["time"] > current_time
        ]
        .sort_values("time")
        .drop_duplicates(
            subset=["city", "time"],
            keep="last"
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Need at least 24 live context hours
    # and 240 future hours
    # --------------------------------------------------------

    if len(past_live) < 24:

        raise HTTPException(
            status_code=503,
            detail=(
                "Open-Meteo returned insufficient "
                "live context data."
            )
        )

    if len(future_live) < 240:

        raise HTTPException(
            status_code=503,
            detail=(
                "Open-Meteo returned insufficient "
                "future forecast data. "
                f"Expected 240 hours, "
                f"got {len(future_live)}."
            )
        )

    # --------------------------------------------------------
    # Historical data
    # --------------------------------------------------------

    historical_city_df = historical_df[
        historical_df["city"] == city
    ].copy()

    if historical_city_df.empty:

        raise HTTPException(
            status_code=404,
            detail=f"No historical data found for {city}."
        )

    # --------------------------------------------------------
    # Required historical columns
    # --------------------------------------------------------

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

    historical_city_df = (
        historical_city_df[
            historical_columns
        ]
        .copy()
    )

    historical_city_df["time"] = pd.to_datetime(
        historical_city_df["time"],
        format="mixed"
    )

    # --------------------------------------------------------
    # Combine historical + LIVE past/current data
    # --------------------------------------------------------

    model_history = pd.concat(
        [
            historical_city_df,
            past_live
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

    # --------------------------------------------------------
    # Exactly next 240 LIVE forecast hours
    # --------------------------------------------------------

    future_forecast = (
        future_live
        .iloc[:240]
        .copy()
        .reset_index(drop=True)
    )

    if len(future_forecast) != 240:

        raise HTTPException(
            status_code=503,
            detail=(
                "Unable to obtain exactly "
                "240 future forecast hours."
            )
        )

    return (
        model_history,
        future_forecast
    )


# ============================================================
# 10-DAY FORECAST ENDPOINT
# ============================================================

@app.get("/predict/10days/{city}")
def predict_next_10_days(
    city: str,
    current_user: dict = Depends(get_current_user)
):

    city = normalize_city(city)

    try:

        return predict_next_10_days_internal(
            city
        )

    except HTTPException:

        raise

    except Exception as e:

        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "10-day forecast failed: "
                f"{type(e).__name__}: {str(e)}"
            )
        )


# ============================================================
# 10-DAY GRU FORECAST INTERNAL FUNCTION
# ============================================================

def predict_next_10_days_internal(city: str):

    # --------------------------------------------------------
    # Get:
    #
    # Historical data
    # +
    # Current LIVE context
    # +
    # Future LIVE Open-Meteo forecast
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
        # Create features
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
                    "Not enough feature rows "
                    "to create the GRU sequence."
                )
            )

        # ----------------------------------------------------
        # Latest 24-hour sequence
        # ----------------------------------------------------

        latest_sequence = (
            featured_df[
                FEATURE_COLUMNS
            ]
            .tail(TIME_STEPS)
            .to_numpy(dtype=float)
        )

        if not np.isfinite(
            latest_sequence
        ).all():

            raise HTTPException(
                status_code=500,
                detail=(
                    "Invalid numerical values "
                    "found in GRU input features."
                )
            )

        # ----------------------------------------------------
        # Scale
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
        # Corresponding LIVE Open-Meteo future row
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

            "time": str(
                forecast_time
            ),

            "predicted_temperature": round(
                predicted_temperature,
                2
            )
        })

        # ----------------------------------------------------
        # Add actual Open-Meteo future weather variables
        # to the working history.
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
    # Convert hourly predictions to daily forecasts
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

    for day_number, (
        date,
        group
    ) in enumerate(
        prediction_df.groupby("date"),
        start=1
    ):

        daily_forecast.append({

            "day": day_number,

            "date": str(
                date
            ),

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

        "forecast_days": len(
            daily_forecast
        ),

        "forecast_hours": len(
            predictions
        ),

        "time_steps": TIME_STEPS,

        "last_data_time": str(
            model_history.iloc[-1]["time"]
        ),

        "daily_forecast": daily_forecast
    }