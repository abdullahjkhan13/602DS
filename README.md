# 602DS — WMATA Metrorail and Weather Conditions

MSML602 / DATA602 group project (Group 2: Duckwoo Kwon, Junhyung Han, Abdullah Khan).

**Research question:** How do weather conditions affect service on WMATA Metrorail, and
how does that effect differ by line, time of day, and station?

**Unit of analysis (final dataset):** one train arrival event at a WMATA station, for a
specific line and direction — with station, line, direction, arrival time, observed
headway, and scheduled headway, joined to the weather and rail incidents in effect at
that time.

Because WMATA's real-time API only exposes a rolling set of *predictions* (not a history
of arrivals), arrival events have to be reconstructed after the fact from repeated
snapshots. That is why collection runs on a schedule and appends to the raw files.

---

## Repository layout

```
602DS/
├── src/
│   ├── main.py               # runs all four collectors in sequence
│   ├── collect_wmata.py      # real-time train predictions  -> data/raw/wmata_predictions.csv
│   ├── collect_incidents.py  # rail incidents / alerts      -> data/raw/wmata_incidents.csv
│   ├── collect_weather.py    # current weather (Open-Meteo) -> data/raw/weather.csv
│   └── collect_gtfs.py       # static GTFS schedule feed    -> data/raw/wmata_gtfs.zip
└── data/
    ├── raw/                  # append-only snapshots (git-ignored)
    └── processed/            # derived tables (git-ignored)
```

Everything under `data/` is git-ignored. Raw data is not committed; collaborators
regenerate it by running the collectors.

## Setup

Requires Python 3.9+ and a free WMATA developer API key
(https://developer.wmata.com/). Open-Meteo needs no key.

```bash
git clone https://github.com/abdullahjkhan13/602DS.git
cd 602DS

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install requests pandas python-dotenv
```

Create the data directories — the collectors do **not** create them, and will fail with
`FileNotFoundError` if they are missing:

```bash
mkdir -p data/raw data/processed
```

Create a `.env` file in the repository root:

```
WMATA_API_KEY=your_key_here
```

`.env` is git-ignored. Do not commit your key.

## Usage

Run all four collectors:

```bash
python src/main.py
```

Or run one at a time:

```bash
python src/collect_wmata.py
```

The three CSV collectors **append**, writing a header only on first run, so each
invocation adds one snapshot to the growing time series. `collect_gtfs.py` **overwrites**
`wmata_gtfs.zip` — the static schedule only needs refreshing when WMATA publishes a new
feed version.

To build a usable dataset, `src/main.py` needs to run on a schedule (every 1–2 minutes
during collection windows; see *Scheduling* below).

---

## Data sources

| Source | Endpoint | Auth | Cadence |
|---|---|---|---|
| WMATA Real-Time Rail Predictions | `StationPrediction.svc/json/GetPrediction/All` | API key header | every run |
| WMATA Rail Incidents | `Incidents.svc/json/Incidents` | API key header | every run |
| WMATA Rail GTFS (static) | `gtfs/rail-gtfs-static.zip` | API key header | occasional refresh |
| Open-Meteo Current Conditions | `api.open-meteo.com/v1/forecast` | none | every run |

Weather is currently pulled for a single point — Metro Center (38.8983, -77.0281) — as a
system-wide proxy. Per-station or multi-point weather is an open design question (see
*Known gaps*).

## Raw schemas

### `data/raw/wmata_predictions.csv`

One row per predicted train arrival, per snapshot.

| Field | Type | Description |
|---|---|---|
| `Car` | string | Number of cars in the train |
| `Destination` | string | Short destination name |
| `DestinationCode` | string | Destination station code |
| `DestinationName` | string | Full destination name |
| `Group` | string | Platform / direction group ("1" or "2") |
| `Line` | string | Metrorail line code (RD, BL, YL, OR, GR, SV) |
| `LocationCode` | string | Station code |
| `LocationName` | string | Station name |
| `Min` | string | Minutes to arrival, or a status (`ARR`, `BRD`, `---`) |
| `snapshot_ts` | datetime (UTC) | When the snapshot was collected — added by us, not from the API |

`Min` is a string, not a number: `ARR` (arriving), `BRD` (boarding), and `---`
(no prediction) all appear and must be handled during processing.

### `data/raw/wmata_incidents.csv`

One row per active incident, per snapshot. An incident that stays open appears in
multiple snapshots, distinguished by `snapshot_ts`.

| Field | Type | Description |
|---|---|---|
| `IncidentID` | string | WMATA incident identifier |
| `Description` | string | Free-text description |
| `IncidentType` | string | Incident category |
| `LinesAffected` | string | Semicolon-delimited line codes |
| `DateUpdated` | datetime | Last update time reported by WMATA |
| `snapshot_ts` | datetime (UTC) | When the snapshot was collected |

### `data/raw/weather.csv`

One row per snapshot.

| Field | Type | Description |
|---|---|---|
| `time` | datetime (UTC) | Observation time reported by Open-Meteo |
| `temperature_2m` | float | Air temperature at 2 m (°C) |
| `precipitation` | float | Total precipitation (mm) |
| `rain` | float | Rain (mm) |
| `snowfall` | float | Snowfall (cm) |
| `wind_speed_10m` | float | Wind speed at 10 m (km/h) |
| `wind_gusts_10m` | float | Wind gusts at 10 m (km/h) |
| `weather_code` | int | WMO weather interpretation code |
| `latitude` / `longitude` | float | Query location (Metro Center) |
| `snapshot_ts` | datetime (UTC) | When the snapshot was collected |

### `data/raw/wmata_gtfs.zip`

Standard GTFS static feed — `stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`,
`calendar.txt`, and related files. `stop_times.txt` is the source of scheduled headways;
`stops.txt` maps GTFS stop IDs to WMATA station codes and provides station coordinates.

---

## Status

### Done — raw collection
- [x] Real-time rail predictions, appended with `snapshot_ts`
- [x] Rail incidents, appended with `snapshot_ts`
- [x] Current weather from Open-Meteo, appended with `snapshot_ts`
- [x] Static GTFS feed download
- [x] Single entry point (`src/main.py`) running all four

### Next — processing and analysis
- [ ] **Scheduling.** Automate `src/main.py` so snapshots accumulate; nothing useful can
      be derived from a handful of manual runs.
- [ ] **Arrival event reconstruction.** Collapse consecutive prediction snapshots into
      discrete arrival events (e.g. detect the `Min` countdown reaching `ARR`/`BRD`, or
      a train disappearing from the board) keyed by station, line, direction, and
      destination. This is the core transformation and the main technical risk.
- [ ] **Observed headway.** Difference between consecutive reconstructed arrivals at the
      same station / line / direction.
- [ ] **Scheduled headway.** Parse `stop_times.txt` + `calendar.txt` from the GTFS zip,
      resolve the service calendar for each date, and compute the scheduled gap for the
      matching time window.
- [ ] **Station identifier crosswalk.** Map WMATA `LocationCode` to GTFS `stop_id` —
      the two feeds do not use the same identifiers.
- [ ] **Joins.** Attach weather (nearest snapshot in time) and incidents (active on the
      line at the arrival time) to each arrival event.
- [ ] **Time handling.** Everything is stored in UTC; local time of day and peak/off-peak
      classification need `America/New_York` with DST handled correctly.
- [ ] **Analysis.** Delay/headway deviation vs. weather, broken out by line, station, and
      time of day.
- [ ] **Pilot validation.** Confirm the schema holds and the three sources actually join,
      per the pilot plan in the proposal.

### Known gaps in the current code
- No `requirements.txt` / `environment.yml` — dependencies are documented here only.
- No `.env.example`.
- `data/raw/` and `data/processed/` are not created automatically and are not tracked, so
  a fresh clone fails until the directories are made by hand.
- No retry or backoff. A single failed request raises and aborts the whole run,
  including the collectors that would have succeeded after it.
- No deduplication. Re-running within the same prediction cycle appends near-duplicate
  rows; dedup is deferred to processing.
- No logging — the collectors print to stdout, which is lost under a scheduler.
- No tests.

## Scheduling

Not yet configured. Prediction data is only useful at high cadence (roughly every 1–2
minutes), since the countdown reconstruction depends on seeing trains step down through
`Min` values. Weather and incidents can be sampled less often. Options under
consideration: `cron` (macOS/Linux), Task Scheduler (Windows), or a GitHub Actions
workflow on a schedule.

## Risks

Carried over from the proposal, with current status:

- **Rate limits.** The free WMATA tier is capped (10 calls/sec, 50,000/day by default).
  High-cadence collection should stay well within this, but the budget should be checked
  before raising cadence.
- **Missing snapshots.** Arrivals between snapshots are invisible, so some events will
  be missed and headways will be over-estimated for those gaps.
- **Timestamp and identifier alignment.** The four sources use different identifiers and
  time conventions; the crosswalk and UTC/local handling above address this.
- **Weather granularity.** One grid point stands in for the whole system; a storm cell
  over one line will be misattributed system-wide.
- **Confounding events.** Delays from mechanical failure, staffing, or scheduled track
  work must be separated out using the incident feed before attributing anything to
  weather.
