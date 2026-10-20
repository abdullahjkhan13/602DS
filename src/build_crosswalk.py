"""Build the WMATA LocationCode <-> GTFS stop crosswalk from a GTFS zip.

stop_times.txt references platform ids (PF_<LocationCode>_<1|2|C>), not station ids,
so platforms are the join target. Station-level ids combine codes at the four transfer
stations (STN_A01_C01), which is why the parent id cannot be used directly.

Usage:  python src/build_crosswalk.py [path/to/gtfs.zip]
"""

import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

from common import RAW_DIR, ROOT, setup_logging

OUT_PATH = ROOT / "reference" / "station_crosswalk.csv"
PLATFORM_RE = re.compile(r"^PF_([A-N][0-9]{2})_(1|2|C)$")

# GTFS route_id -> the line code the real-time prediction API uses.
LINE_CODES = {
    "RED": "RD", "BLUE": "BL", "GREEN": "GR",
    "YELLOW": "YL", "ORANGE": "OR", "SILVER": "SV",
}


def latest_gtfs_zip():
    zips = sorted(RAW_DIR.glob("wmata_gtfs_*.zip"))
    if not zips:
        raise FileNotFoundError(
            f"no wmata_gtfs_*.zip in {RAW_DIR} - run src/collect_gtfs.py first"
        )
    return zips[-1]


def read(z, name):
    return pd.read_csv(z.open(name), dtype=str)


def build(zip_path, logger):
    z = zipfile.ZipFile(zip_path)

    stops = read(z, "stops.txt")
    platforms = stops[stops.location_type == "0"].copy()

    parsed = platforms.stop_id.str.extract(PLATFORM_RE)
    unparsed = platforms.loc[parsed[0].isna(), "stop_id"].tolist()
    if unparsed:
        raise ValueError(f"platform ids did not match expected pattern: {unparsed}")
    platforms["location_code"] = parsed[0]
    platforms["platform_suffix"] = parsed[1]

    stations = stops[stops.location_type == "1"].set_index("stop_id")
    platforms["station_name"] = (
        platforms.parent_station.map(stations.stop_name)
        .str.replace(" METRORAIL STATION", "", regex=False)
        .str.title()
    )
    platforms["stop_lat"] = pd.to_numeric(platforms.parent_station.map(stations.stop_lat))
    platforms["stop_lon"] = pd.to_numeric(platforms.parent_station.map(stations.stop_lon))

    # Which lines actually serve each platform, per the schedule itself.
    trips = read(z, "trips.txt")[["trip_id", "route_id"]]
    served = (
        read(z, "stop_times.txt")[["trip_id", "stop_id"]]
        .merge(trips, on="trip_id")
        .groupby("stop_id")["route_id"]
        .agg(lambda s: ";".join(sorted(set(s))))
    )
    platforms["routes_gtfs"] = platforms.stop_id.map(served)
    platforms["lines_wmata"] = platforms.routes_gtfs.apply(
        lambda r: ";".join(LINE_CODES[x] for x in r.split(";")) if pd.notna(r) else pd.NA
    )

    # A code is "shared" when its station serves another code too (the transfer stations).
    codes_per_station = platforms.groupby("parent_station").location_code.nunique()
    platforms["is_transfer_station"] = (
        platforms.parent_station.map(codes_per_station) > 1
    )

    out = platforms.rename(columns={"stop_id": "gtfs_platform_id",
                                    "parent_station": "gtfs_station_id"})[[
        "location_code", "gtfs_platform_id", "gtfs_station_id", "station_name",
        "platform_suffix", "stop_lat", "stop_lon", "routes_gtfs", "lines_wmata",
        "is_transfer_station",
    ]].sort_values(["location_code", "platform_suffix"]).reset_index(drop=True)

    validate(out, z, logger)
    return out


def validate(out, z, logger):
    if out.gtfs_platform_id.duplicated().any():
        raise ValueError("duplicate platform ids in crosswalk")

    missing_coords = out[out.stop_lat.isna() | out.stop_lon.isna()]
    if not missing_coords.empty:
        raise ValueError(f"platforms missing coordinates: {list(missing_coords.gtfs_platform_id)}")

    # Every stop the schedule references must resolve, or scheduled headways silently
    # lose those stops.
    referenced = set(read(z, "stop_times.txt").stop_id.unique())
    unresolved = referenced - set(out.gtfs_platform_id)
    if unresolved:
        raise ValueError(f"stop_times references {len(unresolved)} stops not in crosswalk: "
                         f"{sorted(unresolved)[:5]}")

    logger.info(
        "validated: %d platforms, %d location codes, %d stations, %d transfer platforms",
        len(out), out.location_code.nunique(), out.gtfs_station_id.nunique(),
        int(out.is_transfer_station.sum()),
    )


def main():
    logger = setup_logging("build_crosswalk")

    zip_path = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_gtfs_zip()
    logger.info("building crosswalk from %s", zip_path.name)

    out = build(zip_path, logger)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    logger.info("wrote %d rows to %s", len(out), OUT_PATH.relative_to(ROOT))


if __name__ == "__main__":
    main()
