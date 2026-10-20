"""Shared helpers for the WMATA/weather collectors."""

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw"
LOG_DIR = ROOT / "logs"

# Transient failures worth retrying; anything else (401, 403, 404) is a real error.
RETRY_STATUS = {429, 500, 502, 503, 504}


def get_api_key():
    key = dotenv_values(ROOT / ".env").get("WMATA_API_KEY")
    if not key:
        raise RuntimeError(
            f"WMATA_API_KEY not found in {ROOT / '.env'} - see README setup section"
        )
    return key


def setup_logging(name):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler = RotatingFileHandler(
        LOG_DIR / f"{name}.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    return logger


def fetch(url, logger, headers=None, params=None, attempts=3, timeout=60):
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status is not None and status not in RETRY_STATUS:
                raise
            if attempt == attempts:
                raise
            backoff = 2**attempt
            logger.warning(
                "request failed (attempt %d/%d, status=%s): %s - retrying in %ds",
                attempt, attempts, status, exc, backoff,
            )
            time.sleep(backoff)


def append_snapshot(df, prefix, snapshot_ts):
    """Append to a per-UTC-day CSV so no single file grows unbounded."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{prefix}_{snapshot_ts:%Y-%m-%d}.csv"
    df.to_csv(path, mode="a", header=not path.exists(), index=False)
    return path
