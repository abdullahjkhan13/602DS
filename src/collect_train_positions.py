import pandas as pd

from common import append_snapshot, fetch, get_api_key, setup_logging

NAME = "train_positions"
URL = "https://api.wmata.com/TrainPositions/TrainPositions"


def main():
    logger = setup_logging(NAME)

    response = fetch(URL, logger, headers={"api_key": get_api_key()},
                     params={"contentType": "json"})
    df = pd.DataFrame(response.json()["TrainPositions"])

    if df.empty:
        logger.warning("no train positions in response")
        return

    snapshot_ts = pd.Timestamp.now(tz="UTC")
    df["snapshot_ts"] = snapshot_ts

    path = append_snapshot(df, NAME, snapshot_ts)
    logger.info("wrote %d rows to %s", len(df), path.name)


if __name__ == "__main__":
    main()
