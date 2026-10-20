"""One-off check: does TrainPositions give us a stable train ID?

If it does, arrival reconstruction can track a known train instead of inferring
identity from a countdown. Delete this script once the decision is recorded.
"""

import json

from common import fetch, get_api_key, setup_logging

URL = "https://api.wmata.com/TrainPositions/TrainPositions"


def main():
    logger = setup_logging("check_train_positions")

    response = fetch(URL, logger, headers={"api_key": get_api_key()},
                     params={"contentType": "json"})
    trains = response.json()["TrainPositions"]

    print(f"\ntrains returned: {len(trains)}")
    print(f"fields: {sorted(trains[0].keys())}\n")
    print("first 3 records:")
    for train in trains[:3]:
        print(json.dumps(train, indent=2))


if __name__ == "__main__":
    main()
