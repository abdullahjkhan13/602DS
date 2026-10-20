import requests
import pandas as pd
from pathlib import Path


def main():
    root = Path(__file__).parent.parent

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        #The latitude and longitude of Metro Center rounded to four decimal places
        "latitude": 38.8983,
        "longitude": -77.0281,
        "current": "temperature_2m,precipitation,rain,snowfall,wind_speed_10m,wind_gusts_10m,weather_code",
        "timezone": "UTC"
    }

    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()

    data = response.json()

    df = pd.DataFrame([data["current"]])
    df["snapshot_ts"] = pd.Timestamp.now(tz="UTC")
    df["latitude"] = params["latitude"]
    df["longitude"] = params["longitude"]

    path = root / "data/raw/weather.csv"

    df.to_csv(path, mode="a", header=not path.exists(), index=False)

    print("Downloaded:", len(df), "rows")


if __name__ == "__main__":
    main()
