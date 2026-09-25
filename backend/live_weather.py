import requests
import time


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


def get_live_weather(latitude, longitude):

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join([
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
        "timezone": "auto"
    }

    for attempt in range(3):

        try:

            response = requests.get(
                url,
                params=params,
                timeout=10
            )

            response.raise_for_status()

            return response.json()

        except requests.RequestException:

            if attempt == 2:
                raise

            time.sleep(2)


def get_latest_hourly_weather(latitude, longitude):

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
        "past_days": 2,
        "forecast_days": 11,
        "timezone": "Asia/Kolkata"
    }

    for attempt in range(3):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=60
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            if attempt == 2:
                raise RuntimeError(
                    f"Open-Meteo request failed after 3 attempts: {e}"
                ) from e
            time.sleep(5)


if __name__ == "__main__":

    for city, coordinates in CITIES.items():

        print("\n" + "=" * 50)
        print(f"LIVE WEATHER: {city}")
        print("=" * 50)

        try:

            weather = get_live_weather(
                coordinates["latitude"],
                coordinates["longitude"]
            )

            current = weather["current"]

            print("Time:", current["time"])
            print("Temperature:", current["temperature_2m"], "°C")
            print("Humidity:", current["relative_humidity_2m"], "%")
            print("Dew Point:", current["dew_point_2m"], "°C")

            print(
                "Apparent Temperature:",
                current["apparent_temperature"],
                "°C"
            )

            print("Precipitation:", current["precipitation"], "mm")
            print("Rain:", current["rain"], "mm")

            print(
                "Surface Pressure:",
                current["surface_pressure"],
                "hPa"
            )

            print("Cloud Cover:", current["cloud_cover"], "%")
            print("Wind Speed:", current["wind_speed_10m"], "km/h")

            print(
                "Wind Direction:",
                current["wind_direction_10m"],
                "°"
            )

            print(
                "Wind Gusts:",
                current["wind_gusts_10m"],
                "km/h"
            )

        except Exception as e:

            print(
                f"Error getting weather for {city}: {e}"
            )