import pandas as pd

from common import append_snapshot, fetch, setup_logging

NAME = "weather"
URL = "https://api.open-meteo.com/v1/forecast"

# Metro Center, rounded to four decimal places.
PARAMS = {
    "latitude": 38.8983,
    "longitude": -77.0281,
    "current": "temperature_2m,precipitation,rain,snowfall,wind_speed_10m,wind_gusts_10m,weather_code",
    "timezone": "UTC",
}


def main():
    logger = setup_logging(NAME)

    response = fetch(URL, logger, params=PARAMS)
    df = pd.DataFrame([response.json()["current"]])

    snapshot_ts = pd.Timestamp.now(tz="UTC")
    df["snapshot_ts"] = snapshot_ts
    df["latitude"] = PARAMS["latitude"]
    df["longitude"] = PARAMS["longitude"]

    path = append_snapshot(df, NAME, snapshot_ts)
    logger.info("wrote %d rows to %s", len(df), path.name)


if __name__ == "__main__":
    main()
