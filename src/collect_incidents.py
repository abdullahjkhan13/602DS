import pandas as pd

from common import append_snapshot, fetch, get_api_key, setup_logging

NAME = "wmata_incidents"
URL = "https://api.wmata.com/Incidents.svc/json/Incidents"


def main():
    logger = setup_logging(NAME)

    response = fetch(URL, logger, headers={"api_key": get_api_key()})
    df = pd.DataFrame(response.json()["Incidents"])

    if df.empty:
        logger.info("no active incidents")
        return

    snapshot_ts = pd.Timestamp.now(tz="UTC")
    df["snapshot_ts"] = snapshot_ts

    path = append_snapshot(df, NAME, snapshot_ts)
    logger.info("wrote %d incidents to %s", len(df), path.name)


if __name__ == "__main__":
    main()
