import pandas as pd
import numpy as np


FEATURE_COLUMNS = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "surface_pressure",
    "cloud_cover",
    "wind_speed_10m",
    "wind_gusts_10m",
    "hour_sin",
    "hour_cos",
    "month_sin",
    "month_cos",
    "wind_direction_sin",
    "wind_direction_cos",
    "temp_lag_1",
    "temp_lag_3",
    "temp_lag_6",
    "temp_lag_24",
    "humidity_lag_1",
    "pressure_lag_1",
    "temp_rolling_mean_3",
    "temp_rolling_mean_6",
    "temp_rolling_std_6",
]


def create_features(df):
    df = df.copy()

    # Convert time column
    df["time"] = pd.to_datetime(df["time"] ,  format="mixed")

    # Sort by city and time
    df = df.sort_values(["city", "time"]).reset_index(drop=True)

    # Time features
    df["hour"] = df["time"].dt.hour
    df["month"] = df["time"].dt.month

    # Cyclic time features
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    # Wind direction features
    df["wind_direction_sin"] = np.sin(
        2 * np.pi * df["wind_direction_10m"] / 360
    )

    df["wind_direction_cos"] = np.cos(
        2 * np.pi * df["wind_direction_10m"] / 360
    )

    # Lag features
    df["temp_lag_1"] = (
        df.groupby("city")["temperature_2m"].shift(1)
    )

    df["temp_lag_3"] = (
        df.groupby("city")["temperature_2m"].shift(3)
    )

    df["temp_lag_6"] = (
        df.groupby("city")["temperature_2m"].shift(6)
    )

    df["temp_lag_24"] = (
        df.groupby("city")["temperature_2m"].shift(24)
    )

    df["humidity_lag_1"] = (
        df.groupby("city")["relative_humidity_2m"].shift(1)
    )

    df["pressure_lag_1"] = (
        df.groupby("city")["surface_pressure"].shift(1)
    )

    # Rolling features
    df["temp_rolling_mean_3"] = (
        df.groupby("city")["temperature_2m"]
        .transform(lambda x: x.rolling(window=3).mean())
    )

    df["temp_rolling_mean_6"] = (
        df.groupby("city")["temperature_2m"]
        .transform(lambda x: x.rolling(window=6).mean())
    )

    df["temp_rolling_std_6"] = (
        df.groupby("city")["temperature_2m"]
        .transform(lambda x: x.rolling(window=6).std())
    )

    return df