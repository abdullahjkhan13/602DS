
import requests
import pandas as pd
from pathlib import Path
from dotenv import dotenv_values


def main():
    root = Path(__file__).parent.parent
    api_key = dotenv_values(root / ".env")["WMATA_API_KEY"]

    url = "https://api.wmata.com/Incidents.svc/json/Incidents"

    response = requests.get(url, headers={"api_key": api_key}, timeout=60)
    response.raise_for_status()

    df = pd.DataFrame(response.json()["Incidents"])

    if df.empty:
        print("No incidents found.")
        return

    df["snapshot_ts"] = pd.Timestamp.now(tz="UTC")

    path = root / "data/raw/wmata_incidents.csv"

    df.to_csv(path, mode="a", header=not path.exists(), index=False)

    print("Downloaded:", len(df), "incidents")


if __name__ == "__main__":
    main()
