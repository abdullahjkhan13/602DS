"""Run every collector once. Scheduled collection runs each script separately."""

import sys

import collect_gtfs
import collect_incidents
import collect_weather
import collect_wmata
from common import setup_logging

COLLECTORS = [
    ("predictions", collect_wmata.main),
    ("gtfs", collect_gtfs.main),
    ("incidents", collect_incidents.main),
    ("weather", collect_weather.main),
]


def main():
    logger = setup_logging("main")
    failed = []

    for name, collect in COLLECTORS:
        try:
            collect()
        except Exception:
            logger.exception("collector %r failed", name)
            failed.append(name)

    if failed:
        logger.error("%d of %d collectors failed: %s", len(failed), len(COLLECTORS), ", ".join(failed))
        sys.exit(1)

    logger.info("all collectors succeeded")


if __name__ == "__main__":
    main()
