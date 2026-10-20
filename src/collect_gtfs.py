import requests
from pathlib import Path
from dotenv import dotenv_values


def main():
    root = Path(__file__).parent.parent
    api_key = dotenv_values(root / ".env")["WMATA_API_KEY"]

    url = "https://api.wmata.com/gtfs/rail-gtfs-static.zip"

    response = requests.get(url, headers={"api_key": api_key}, timeout=60)
    response.raise_for_status()

    path = root / "data/raw/wmata_gtfs.zip"
    path.write_bytes(response.content)

    print("GTFS downloaded successfully.")


if __name__ == "__main__":
    main()
