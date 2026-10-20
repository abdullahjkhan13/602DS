import pandas as pd

from common import RAW_DIR, fetch, get_api_key, setup_logging

NAME = "wmata_gtfs"
URL = "https://api.wmata.com/gtfs/rail-gtfs-static.zip"


def main():
    logger = setup_logging(NAME)

    response = fetch(URL, logger, headers={"api_key": get_api_key()})

    # Dated filename: an arrival must be compared against the schedule in force that
    # day, so superseded feeds have to be kept rather than overwritten.
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{NAME}_{pd.Timestamp.now(tz='UTC'):%Y-%m-%d}.zip"
    path.write_bytes(response.content)

    logger.info("wrote %d bytes to %s", len(response.content), path.name)


if __name__ == "__main__":
    main()
