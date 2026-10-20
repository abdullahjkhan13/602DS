"""Probe every endpoint the project might use and report what the API key can reach.

Run this first the moment a key arrives: it tells you in one shot which WMATA products
the key is subscribed to, so a missing subscription surfaces immediately instead of as
silently empty data a day later.

Usage:  python src/verify_access.py
"""

import requests

from common import get_api_key

TIMEOUT = 60

ENDPOINTS = [
    ("Rail Predictions", "https://api.wmata.com/StationPrediction.svc/json/GetPrediction/All",
     None, lambda r: f"{len(r.json()['Trains'])} trains"),
    ("Incidents", "https://api.wmata.com/Incidents.svc/json/Incidents",
     None, lambda r: f"{len(r.json()['Incidents'])} active"),
    ("Train Positions", "https://api.wmata.com/TrainPositions/TrainPositions",
     {"contentType": "json"}, lambda r: f"{len(r.json()['TrainPositions'])} trains"),
    ("Rail Station Info", "https://api.wmata.com/Rail.svc/json/jStations",
     None, lambda r: f"{len(r.json()['Stations'])} stations"),
    ("GTFS static (rail)", "https://api.wmata.com/gtfs/rail-gtfs-static.zip",
     None, lambda r: f"{len(r.content):,} bytes"),
    ("GTFS-RT trip updates", "https://api.wmata.com/gtfs/rail-gtfsrt-tripupdates.pb",
     None, lambda r: f"{len(r.content):,} bytes"),
    ("GTFS-RT vehicle positions", "https://api.wmata.com/gtfs/rail-gtfsrt-vehiclepositions.pb",
     None, lambda r: f"{len(r.content):,} bytes"),
    ("GTFS-RT alerts", "https://api.wmata.com/gtfs/rail-gtfsrt-alerts.pb",
     None, lambda r: f"{len(r.content):,} bytes"),
]


def main():
    headers = {"api_key": get_api_key()}
    reachable = 0

    print(f"\n{'endpoint':<28} {'status':<10} detail")
    print("-" * 70)

    for name, url, params, summarize in ENDPOINTS:
        try:
            response = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
            if response.ok:
                try:
                    detail = summarize(response)
                except Exception as exc:
                    detail = f"200 but unreadable: {exc}"
                print(f"{name:<28} {'OK':<10} {detail}")
                reachable += 1
            elif response.status_code in (401, 403):
                print(f"{name:<28} {'NO ACCESS':<10} key not subscribed to this product")
            else:
                print(f"{name:<28} {response.status_code:<10} {response.text[:60]}")
        except requests.RequestException as exc:
            print(f"{name:<28} {'ERROR':<10} {exc}")

    print("-" * 70)
    print(f"{reachable}/{len(ENDPOINTS)} endpoints reachable\n")

    if reachable < len(ENDPOINTS):
        print("Anything marked NO ACCESS needs that product added to your key at")
        print("https://developer.wmata.com/ -> Products. Add it before starting collection:")
        print("real-time data cannot be backfilled.\n")


if __name__ == "__main__":
    main()
