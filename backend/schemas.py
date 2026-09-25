from pydantic import BaseModel


class WeatherFeatures(BaseModel):
    temperature_2m: float
    relative_humidity_2m: float
    dew_point_2m: float
    apparent_temperature: float
    precipitation: float
    rain: float
    surface_pressure: float
    cloud_cover: float
    wind_speed_10m: float
    wind_gusts_10m: float

    hour_sin: float
    hour_cos: float
    month_sin: float
    month_cos: float

    wind_direction_sin: float
    wind_direction_cos: float

    temp_lag_1: float
    temp_lag_3: float
    temp_lag_6: float
    temp_lag_24: float

    humidity_lag_1: float
    pressure_lag_1: float

    temp_rolling_mean_3: float
    temp_rolling_mean_6: float
    temp_rolling_std_6: float