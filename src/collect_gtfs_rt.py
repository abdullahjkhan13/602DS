"""Collect the rail GTFS-Realtime feeds.

Stores the raw protobuf gzipped rather than decoding now. Decoding is a schema
assumption, and a wrong one loses data permanently; the bytes can be parsed any number
of times later. See ROADMAP Phase 1.3.
"""

import gzip

import pandas as pd

from common import RAW_DIR, fetch, get_api_key, setup_logging

NAME = "gtfs_rt"
BASE = "https://api.wmata.com/gtfs"

FEEDS = {
    "tripupdates": f"{BASE}/rail-gtfsrt-tripupdates.pb",
    "vehiclepositions": f"{BASE}/rail-gtfsrt-vehiclepositions.pb",
    "alerts": f"{BASE}/rail-gtfsrt-alerts.pb",
}


def main():
    logger = setup_logging(NAME)
    headers = {"api_key": get_api_key()}
    snapshot_ts = pd.Timestamp.now(tz="UTC")

    failed = []
    for feed, url in FEEDS.items():
        try:
            response = fetch(url, logger, headers=headers)
        except Exception:
            logger.exception("feed %r failed", feed)
            failed.append(feed)
            continue

        out_dir = RAW_DIR / NAME / feed / f"{snapshot_ts:%Y-%m-%d}"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{feed}_{snapshot_ts:%Y%m%dT%H%M%SZ}.pb.gz"
        path.write_bytes(gzip.compress(response.content))

        logger.info("%s: %d bytes -> %s", feed, len(response.content), path.name)

    if failed:
        raise RuntimeError(f"feeds failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
