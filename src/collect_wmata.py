import pandas as pd

from common import append_snapshot, fetch, get_api_key, setup_logging

NAME = "wmata_predictions"
URL = "https://api.wmata.com/StationPrediction.svc/json/GetPrediction/All"


def main():
    logger = setup_logging(NAME)

    response = fetch(URL, logger, headers={"api_key": get_api_key()})
    df = pd.DataFrame(response.json()["Trains"])

    if df.empty:
        logger.warning("no trains in response")
        return

    snapshot_ts = pd.Timestamp.now(tz="UTC")
    df["snapshot_ts"] = snapshot_ts

    path = append_snapshot(df, NAME, snapshot_ts)
    logger.info("wrote %d rows to %s", len(df), path.name)


if __name__ == "__main__":
    main()
