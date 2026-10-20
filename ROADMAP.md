# Project Roadmap — WMATA Metrorail and Weather Conditions

MSML602 / DATA602, Group 2 — Duckwoo Kwon, Junhyung Han, Abdullah Khan.

This is the master plan: what is finished, and every step between here and the final
deliverable. See [README.md](README.md) for setup and raw data schemas, and the project
proposal for the original framing.

**End goal.** A single analytical dataset where each row is one train arrival event at a
WMATA station (station, line, direction, arrival time, observed headway, scheduled
headway), joined to the weather and rail incidents in effect at that moment — plus an
analysis of how weather affects service, broken out by line, time of day, and station.

**Status legend:** `[x]` done · `[ ]` not started · `[~]` in progress

---

## Phase 0 — Raw data collection (DONE)

- [x] Real-time rail prediction collector (`src/collect_wmata.py`), appending with a
      `snapshot_ts` we add ourselves, since the API does not timestamp responses
- [x] Rail incident collector (`src/collect_incidents.py`), appending with `snapshot_ts`
- [x] Current weather collector (`src/collect_weather.py`), Open-Meteo, Metro Center
      coordinates, appending with `snapshot_ts`
- [x] Static GTFS rail feed download (`src/collect_gtfs.py`)
- [x] Single entry point running all four (`src/main.py`)
- [x] API key handling via git-ignored `.env`
- [x] Repo hygiene: `requirements.txt`, tracked `data/raw/` and `data/processed/`
      directories, documented schemas in the README

**What this means:** acquisition works end to end. Every remaining phase is either
*keeping it running* or *turning snapshots into the unit of analysis.*

---

## Decisions needed before anything else

These block or shape the work downstream. Resolve them as a group, then record the
answers in this file.

- [ ] **Collection end date** — when does data collection stop so analysis can start?
      Everything downstream is sized by this.
- [ ] **Snapshot cadence** for predictions (recommend 60s; see Phase 1).
- [ ] **24/7 or service hours only?** Metrorail runs roughly 05:00–00:00. Overnight
      collection produces almost no arrivals but keeps the pipeline simple.
- [ ] **Add a `TrainPositions` collector?** See Phase 1.3 — this decision cannot be
      deferred, because missed collection cannot be backfilled.
- [ ] **Storage format** — plain appended CSV, daily-partitioned CSV, or Parquet
      (see Phase 1.4).
- [ ] **Owner for each phase below.**

---

## Phase 1 — Make collection continuous and reliable (URGENT)

Nothing else matters until this is done. Real-time prediction data cannot be recovered
after the fact: every hour the scheduler is not running is an hour permanently missing
from the dataset. This is the single highest-priority item in the project.

### 1.1 Scheduling
- [ ] Choose a mechanism: `cron` (macOS/Linux), Task Scheduler (Windows), or a GitHub
      Actions scheduled workflow
- [ ] Decide cadence per source and split `main.py` accordingly — they do not all need
      the same frequency:
      - predictions: every 60s (required for countdown reconstruction, Phase 2)
      - incidents: every 5 min
      - weather: every 15 min (Open-Meteo refreshes roughly this often; faster is waste)
      - GTFS: weekly, or whenever WMATA publishes a new feed
- [ ] Confirm it survives sleep/reboot on whichever machine hosts it
- [ ] Verify the WMATA rate budget: the free tier is limited (commonly 10 calls/sec and
      50,000/day). At 60s cadence, predictions cost ~1,440 calls/day — comfortably
      inside the cap, but confirm against your key's actual tier before raising cadence.

> **Trade-off worth discussing:** a laptop on cron is simplest but dies when the laptop
> does. GitHub Actions runs unattended but its scheduled jobs are best-effort and can be
> delayed under load, which adds jitter to `snapshot_ts`. A always-on machine is the
> safest if anyone has one.

### 1.2 Robustness
- [ ] Wrap each collector call in `main.py` so one failure does not abort the others —
      right now an exception in `collect_wmata` prevents weather and incidents from
      running at all
- [ ] Add retry with backoff on transient HTTP failures (timeouts, 5xx, 429)
- [ ] Replace `print` with `logging` to a rotating file — stdout is lost under a
      scheduler, so failures would currently be silent
- [ ] Record failed runs so gaps in the time series are explainable later

### 1.3 Evaluate the `TrainPositions` endpoint — time-sensitive
`GetPrediction` returns no train identifier, which is what makes arrival reconstruction
(Phase 2) hard and approximate. WMATA publishes a separate real-time endpoint,
`TrainPositions`, which is documented as including a train ID, track circuit ID,
line, direction, destination, and seconds-at-location.

- [ ] Verify the endpoint, its fields, and its rate cost against your API key
- [ ] If it carries a stable train ID, add a collector for it **now** — tracking a train
      by ID is far more reliable than inferring identity from a countdown, and it would
      substantially de-risk Phase 2
- [ ] If adopted, treat it as a supplement, not a replacement: predictions remain the
      station-level source, positions become the identity source

This is listed in Phase 1 rather than Phase 2 on purpose. Reconstruction can be written
later; the data to support it can only be captured in real time.

### 1.4 Storage
- [ ] Estimate growth: `GetPrediction/All` returns on the order of several hundred rows
      per call. At 60s cadence this is roughly 400k–600k rows/day, i.e. tens to hundreds
      of MB of CSV per day. Measure your actual rate after a day of collection.
- [ ] Decide on partitioning — one file per day (`wmata_predictions_2026-10-21.csv`)
      rather than one unbounded file, so nothing has to be fully re-read to inspect a
      single day
- [ ] Consider Parquet for the processed layer (smaller, typed, much faster to load)
- [ ] Confirm the repo stays clean — raw data must not be committed

> This directory is inside OneDrive. Continuous appends to large files in a synced folder
> can cause sync churn or file locking. Check whether `data/` should be excluded from
> OneDrive sync.

---

## Phase 2 — Arrival event reconstruction (CORE TECHNICAL WORK)

This is the heart of the project and its biggest technical risk. The API gives a rolling
board of *predictions*; the unit of analysis is an *arrival*. Nobody hands you arrivals —
they have to be inferred from how predictions change across consecutive snapshots.

**The problem:** at each snapshot, for every station and platform group, you see the next
few trains with a `Min` value. There is no train ID (unless Phase 1.3 provides one). To
say "a train arrived at 14:32," you must recognize the *same* train across snapshots as
its `Min` counts down, and detect the moment it arrives.

- [ ] **Load and normalize raw predictions.** Parse `snapshot_ts`, handle the `Min`
      column's non-numeric values (`ARR` arriving, `BRD` boarding, `---` and empty for
      no prediction), drop or flag rows with no usable prediction
- [ ] **Define the tracking key.** Group observations by
      `(LocationCode, Group, Line, DestinationCode)` — within a group, trains are ordered
      by `Min`
- [ ] **Link observations across snapshots.** For each key, match a prediction at
      snapshot *t+1* to one at *t* where `Min` has decreased by roughly the elapsed time.
      Start with greedy nearest-match; escalate to an assignment algorithm if it proves
      too error-prone
- [ ] **Detect the arrival.** Candidate rules — evaluate against reality, do not assume:
      - last snapshot where the train shows `BRD`
      - first snapshot where it shows `ARR`
      - the train disappearing from the board after a low `Min`
- [ ] **Assign an arrival timestamp** and record its uncertainty. With 60s snapshots,
      resolution is ±1 minute at best; carry that as a column rather than pretending to
      precision you do not have
- [ ] **Handle the edge cases**, each of which silently corrupts headways if ignored:
      - `Min` jumping upward when WMATA revises a prediction
      - trains held at a platform (`BRD` persisting across many snapshots)
      - trains vanishing without arriving (offloaded, rerouted, single-tracking)
      - two trains to the same destination queued at the same platform
      - gaps in collection (scheduler downtime) producing false "disappearances"
      - end-of-line terminals, where arrival and departure behave differently
- [ ] **Validate.** Spot-check a handful of station-hours by hand against the raw
      snapshots. Do not proceed to headways until reconstruction is trusted — every
      downstream number inherits its errors
- [ ] **Output** `data/processed/arrival_events.parquet`: one row per reconstructed
      arrival, with a confidence or method flag

### 2.1 Observed headway
- [ ] Sort arrivals by station / line / direction / time
- [ ] Observed headway = gap between consecutive arrivals
- [ ] Flag headways spanning a collection gap as unreliable rather than real
- [ ] Decide handling for the first arrival of each service day (no predecessor)

---

## Phase 3 — GTFS schedule processing

Produces the scheduled baseline that observed service is measured against.

- [ ] Unzip and load `stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`,
      `calendar.txt`, `calendar_dates.txt`
- [ ] Resolve the service calendar: which `service_id`s run on a given date, including
      `calendar_dates.txt` exceptions (holidays)
- [ ] Handle GTFS times past midnight — `25:14:00` is valid GTFS meaning 01:14 on the
      following day, and naive parsing will throw or silently mangle late-night service
- [ ] Build scheduled arrivals per stop / route / direction / service date
- [ ] **Scheduled headway** = gap between consecutive scheduled arrivals at the same
      stop / route / direction, resolved for the time window containing each observed
      arrival
- [ ] Note the feed version and collection date — WMATA revises schedules, and an
      arrival must be compared against the schedule in force *that day*, not the latest
      one. If the feed changes mid-collection, keep both.
- [ ] Output `data/processed/scheduled_headways.parquet`

---

## Phase 4 — Identifier crosswalk

The four sources do not share identifiers. Nothing joins until this exists.

- [ ] **Station:** WMATA `LocationCode` (e.g. `A01`) ↔ GTFS `stop_id`. Rail GTFS
      typically has platform-level stops with a `parent_station`; decide which level is
      the join target
- [ ] **Direction:** WMATA `Group` (`1`/`2`) ↔ GTFS `direction_id` (`0`/`1`). **Do not
      assume these align.** Validate empirically per line — a silent mismatch here
      reverses direction for an entire line and quietly invalidates every headway
      computed from it
- [ ] **Line:** WMATA line code (`RD`, `BL`, `YL`, `OR`, `GR`, `SV`) ↔ GTFS `route_id`
- [ ] Handle shared-track stations where multiple lines serve one platform
- [ ] **Validate coverage:** assert every station code appearing in the predictions maps
      to exactly one GTFS stop, and fail loudly on unmapped codes
- [ ] Store as a versioned reference file (e.g. `reference/station_crosswalk.csv`)
      committed to the repo — it is small, stable, and hand-verified, so it belongs in
      git rather than being regenerated

### 4.1 Station attributes (enables the "differs by station/line" analysis)
- [ ] Pull station coordinates from GTFS `stops.txt`
- [ ] **Flag above-ground vs. underground segments.** This is likely the strongest
      predictor of weather sensitivity in the entire project: underground platforms are
      insulated from rain, snow, and heat, while above-ground track and rolling stock are
      not. Derive from WMATA station data or code manually — there are only 98 stations
- [ ] Note terminals, transfer stations, and single-track-prone segments

---

## Phase 5 — Weather processing and join

- [ ] Deduplicate — at 15-minute collection against an endpoint that updates at a similar
      rate, consecutive rows will repeat; key on the Open-Meteo `time` field, not
      `snapshot_ts`
- [ ] **Decide spatial granularity.** Currently one point (Metro Center) stands in for
      the whole system. Options: keep the single proxy and state the limitation; sample
      several points across the service area (e.g. one per line, or per outlying
      terminal); or interpolate per station. More points cost nothing in API terms but
      add pipeline complexity
- [ ] **Evaluate the Open-Meteo historical/archive API as a backfill.** Unlike the
      transit data, weather *can* be recovered retroactively, and an archive pull would
      give hourly history for any coordinates. This substantially de-risks weather
      coverage and may make per-station weather cheap
- [ ] **Join to arrival events** by nearest timestamp — a backward as-of join with an
      explicit tolerance (e.g. 30 min), so an arrival never silently inherits weather
      from hours away
- [ ] **Derive features** for analysis:
      - binary conditions: raining, snowing, freezing, high wind
      - intensity bins rather than raw mm, since effects are unlikely to be linear
      - **lagged/cumulative measures** — precipitation over the prior 1h/3h, snow
        accumulation. Service impact follows accumulated conditions, not the instant
        reading; an inch of snow that fell two hours ago matters more than whether it
        happens to be falling right now. This is likely where the real signal lives
      - heat: temperature above thresholds relevant to heat restrictions
- [ ] Output `data/processed/weather_clean.parquet`

---

## Phase 6 — Incident processing and join

Incidents are the main confounder: a delay during a storm may have been caused by a
broken rail, and attributing it to weather would be wrong.

- [ ] **Collapse snapshots into incident intervals.** An open incident reappears in every
      snapshot; reduce to one row per `IncidentID` with `first_seen` / `last_seen`
- [ ] Parse `LinesAffected` — semicolon-delimited, often with stray whitespace — into
      one row per incident × line
- [ ] Classify `IncidentType` / `Description` into useful categories (mechanical, track,
      police/medical, weather-related, scheduled work)
- [ ] **Join to arrival events:** flag each arrival with any incident active on its line
      at that time
- [ ] Decide the analytical role: control variable in the model, exclusion filter, or
      both as a robustness check. **Note the subtlety:** some incidents are *caused* by
      weather, so controlling for all incidents would absorb part of the very effect
      being measured. Separate weather-caused incidents from independent ones
- [ ] Output `data/processed/incidents_clean.parquet`

---

## Phase 7 — Build the analytical dataset

- [ ] Assemble one row per arrival event joining Phases 2–6
- [ ] **Derived service metrics:**
      - headway deviation = observed − scheduled
      - excess wait time (the passenger-weighted standard, more defensible than raw
        headway difference)
      - a bunching / gapping indicator
- [ ] **Time features, DST-safe.** Everything is stored UTC; convert to
      `America/New_York` for time-of-day and peak classification. The collection period
      spans the November DST change, so naive UTC offsets will shift an hour of data into
      the wrong peak bucket
- [ ] Peak / off-peak per WMATA's own definitions; day of week; weekday vs weekend
- [ ] Write a **data dictionary** for every column — required for the deliverable and
      genuinely useful for the group
- [ ] Output `data/processed/analysis_dataset.parquet` (plus CSV if the report needs it)

---

## Phase 8 — Validation and QA

Do this before analysis, not after. A plausible-looking regression on a broken join is
the worst outcome available.

- [ ] **Collection coverage:** find gaps in `snapshot_ts`; quantify uptime; document
      every outage
- [ ] **Plausibility bounds:** headways outside roughly 1–30 minutes are suspect;
      investigate rather than silently clip
- [ ] **Volume check:** reconstructed arrivals per station per day vs. GTFS scheduled
      trips. Large shortfalls mean reconstruction is dropping trains
- [ ] **Direction check:** confirm the `Group` ↔ `direction_id` mapping against known
      geography (a train to Shady Grove should be northbound on the Red Line)
- [ ] **Join integrity:** no arrival lacking weather; no unexplained nulls; row counts
      preserved through each merge
- [ ] **Pilot validation**, per the proposal: analyze 5–10% of the target dataset end to
      end and confirm the schema holds before committing to full-scale processing
- [ ] Record schema changes the pilot forces — the proposal explicitly anticipates this

---

## Phase 9 — Exploratory data analysis

- [ ] Missingness and outlier profile across all sources
- [ ] Distribution of headway deviation overall, by line, by station, by hour
- [ ] Baseline service patterns in *good* weather — the comparison point for everything
- [ ] **Weather coverage audit — do this early.** Check what conditions the collection
      window actually contains. If the period includes no snow, the snow hypothesis is
      untestable no matter how good the pipeline is, and the research question must lean
      on rain, wind, and temperature instead. Find this out now, not while writing the
      report
- [ ] Incident frequency and overlap with weather events
- [ ] Visualizations for the report

---

## Phase 10 — Analysis

Answering the research question: *how do weather conditions affect WMATA service, and how
does that differ by line, time of day, and station?*

- [ ] **Descriptive:** mean headway deviation and excess wait by weather condition, with
      uncertainty intervals
- [ ] **Modeling:** regress headway deviation on weather features, controlling for line,
      station, hour of day, day of week, and incidents. Observations within a
      station-hour are correlated, so use clustered standard errors or a mixed model —
      naive OLS will understate uncertainty
- [ ] **Heterogeneity — this is the differentiating analysis:**
      - **above-ground vs. underground** (Phase 4.1): the cleanest natural comparison
        available, and close to a built-in control group
      - by line — lines differ in how much of their track is exposed
      - by time of day — peak service has less slack to absorb disruption
      - by station — terminals and transfers behave differently
- [ ] **Robustness:** with and without incident controls; alternative arrival-detection
      rules from Phase 2; excluding low-confidence arrivals
- [ ] **State the limitations honestly:** observational data, a short collection window,
      a single weather point, approximate arrival times, and no causal identification.
      Correlation is the defensible claim, and the proposal's stated goal

---

## Phase 11 — Deliverables

- [ ] Final report / notebook: question, data, methods, results, limitations
- [ ] Reproducibility: anyone should be able to clone, install, collect, and rebuild
- [ ] Final README pass
- [ ] Data dictionary for the processed dataset
- [ ] Code cleanup and consistent structure
- [ ] Presentation materials, if required
- [ ] Confirm all course-specific submission requirements

---

## Suggested sequencing

Phase 1 is the only true emergency — it is the one task where delay destroys data that
cannot be recovered. Phases 3 and 4 depend only on the static GTFS feed, so they can be
built immediately and in parallel with collection; there is no reason to wait. Phase 2 is
the long pole and should start as soon as a few days of snapshots exist to test against.

| Order | Work | Depends on | Notes |
|---|---|---|---|
| 1 | Phase 1 — scheduling and reliability | — | Start today; every hour costs data |
| 2 | Phases 3 + 4 — GTFS and crosswalk | GTFS zip only | Parallel with collection |
| 3 | Phase 2 — arrival reconstruction | A few days of snapshots | Longest and riskiest |
| 4 | Phases 5 + 6 — weather and incidents | Phase 2 output | Parallelizable |
| 5 | Phase 7 — analytical dataset | Phases 2–6 | |
| 6 | Phase 8 — validation | Phase 7 | Gate before analysis |
| 7 | Phases 9 + 10 — EDA and analysis | Phase 8 | |
| 8 | Phase 11 — deliverables | All | |

Good parallel split across three people: one owns collection infrastructure (Phase 1),
one owns GTFS and the crosswalk (Phases 3–4), one owns reconstruction (Phase 2). The
phases converge at Phase 7.

---

## Risk register

Carried from the proposal, updated with current status and mitigation.

| Risk | Status | Mitigation |
|---|---|---|
| Collection not yet automated — data lost permanently | **Open, urgent** | Phase 1.1, today |
| Arrival reconstruction proves unreliable | **Open, high** | Phase 1.3 (`TrainPositions`), careful Phase 2 validation |
| Rate limits / key expiry | Monitored | Stay well inside quota; log failures (Phase 1.2) |
| Missed snapshots between arrivals | Expected | 60s cadence; flag gap-spanning headways (Phase 2.1) |
| Timestamp / identifier misalignment | **Open** | Phase 4 crosswalk with hard validation; UTC throughout, DST-safe conversion |
| Weather granularity — one point for the system | **Open** | Phase 5: more sample points and/or archive backfill |
| Confounding non-weather incidents | **Open** | Phase 6 controls, separating weather-caused incidents |
| Collection window may contain no severe weather | **Open, underrated** | Audit early (Phase 9); fall back to rain/heat/wind if snow never appears |
| Raw data volume outgrowing CSV | **Open** | Phase 1.4 partitioning / Parquet |
