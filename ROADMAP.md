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

## Where we are right now

*Last updated 2026-10-20.*

**Blocked on one thing: the WMATA API key.** Everything that can be built without it has
been. When the key arrives, collection starts in four commands (see the README) — no code
needs writing first.

| Phase | State |
|---|---|
| 0 — Collection code | Done, six collectors |
| 1 — Reliability, scheduling, storage | Done and scripted; **waiting on key to run** |
| 2 — Arrival reconstruction | Not started; approach may change — see 1.3 |
| 3 — GTFS schedule parsing | Feed structure mapped; parsing not written |
| 4 — Crosswalk | Built and validated; needs re-run on the live feed |
| 5–11 | Not started |

**Three findings so far that changed the plan:**

1. **WMATA publishes GTFS-Realtime rail feeds** (Phase 1.3). If `TripUpdates` carries
   real arrival times keyed by `trip_id`, most of Phase 2 collapses — observed and
   scheduled arrivals would share an identifier instead of being matched by inference.
   Collectors are written and will run from day one; the decision gets made on real data.
2. **The crosswalk had a silent-failure trap** (Phase 4). Joining at GTFS *station* level
   would have dropped Metro Center, Gallery Place, L'Enfant Plaza and Fort Totten without
   error. Joining at platform level avoids it. Solved and validated.
3. **The collection window almost certainly contains no testable snow** (Phase 9). Seven
   years of history give a median of 4 snow hours in this calendar window. Rain, wind and
   freezing temperatures are all well-powered; snow is not. **This affects the research
   question as written** and should be discussed as a group.

---

## Phase 0 — Raw data collection (DONE)

- [x] Real-time rail prediction collector (`src/collect_wmata.py`), appending with a
      `snapshot_ts` we add ourselves, since the API does not timestamp responses
- [x] Rail incident collector (`src/collect_incidents.py`), appending with `snapshot_ts`
- [x] Current weather collector (`src/collect_weather.py`), Open-Meteo, Metro Center
      coordinates, appending with `snapshot_ts`
- [x] Static GTFS rail feed download (`src/collect_gtfs.py`), dated per download
- [x] GTFS-Realtime collector (`src/collect_gtfs_rt.py`) — trip updates, vehicle
      positions and alerts, stored as gzipped raw protobuf
- [x] Train position collector (`src/collect_train_positions.py`)
- [x] Single entry point running all six (`src/main.py`), with per-collector failure
      isolation
- [x] API key handling via git-ignored `.env`, with a committed `.env.example`
- [x] Repo hygiene: `requirements.txt`, tracked `data/raw/` and `data/processed/`
      directories, documented schemas in the README

**What this means:** acquisition is written and tested for every source we might use.
Every remaining phase is either *keeping it running* or *turning snapshots into the unit
of analysis.*

---

## Decisions needed before anything else

These block or shape the work downstream. Resolve them as a group, then record the
answers in this file.

**Still open:**

- [ ] **Collection end date** — when does data collection stop so analysis can start?
      Everything downstream is sized by this.
- [ ] **24/7 or service hours only?** Metrorail runs roughly 05:00–00:00. Overnight
      collection produces almost no arrivals but keeps the pipeline simple.
- [ ] **Which machine hosts collection?** A laptop on a scheduler stops when it sleeps;
      an always-on machine is far safer. This gates starting collection.
- [ ] **Does the research question still lead with snow?** The climatology says it
      cannot be answered in this window (see *Where we are right now*). Reframing around
      rain, wind and freezing temperatures is the realistic option.
- [ ] **Owner for each phase below.**

**Resolved:**

- [x] **Snapshot cadence** — 60s for the three real-time sources, 5 min incidents,
      15 min weather, weekly GTFS. Encoded in `setup_scheduler.ps1`.
- [x] **Collect `TrainPositions` and GTFS-RT?** Yes, both, from day one. Neither can be
      backfilled, and Phase 1.3 cannot be settled without real data.
- [x] **Storage format** — daily-partitioned CSV for tabular sources, gzipped raw
      protobuf for GTFS-RT, Parquet for the processed layer.

---

## Phase 1 — Make collection continuous and reliable (URGENT)

Nothing else matters until this is done. Real-time prediction data cannot be recovered
after the fact: every hour the scheduler is not running is an hour permanently missing
from the dataset. This is the single highest-priority item in the project.

### 1.1 Scheduling
- [x] Mechanism chosen and scripted — `setup_scheduler.ps1` registers every collector as
      a Windows scheduled task, and refuses to run without a `.venv` and `.env`
- [x] Collectors written for all candidate sources, so collection can start the moment a
      key exists: predictions, GTFS-RT, train positions, incidents, weather, GTFS static
- [x] `src/verify_access.py` — probes every endpoint and reports which the key can reach
- [ ] **Run it.** Blocked only on the API key
- [x] Cadence per source, encoded in `setup_scheduler.ps1`:
      - predictions, GTFS-RT, train positions: every 60s
      - incidents: every 5 min
      - weather: every 15 min (Open-Meteo refreshes roughly this often; faster is waste)
      - GTFS static: weekly
- [ ] Confirm it survives sleep/reboot on whichever machine hosts it
- [ ] Verify the WMATA rate budget: the free tier is limited (commonly 10 calls/sec and
      50,000/day). At 60s cadence, predictions cost ~1,440 calls/day — comfortably
      inside the cap, but confirm against your key's actual tier before raising cadence.

> **Trade-off worth discussing:** a laptop on cron is simplest but dies when the laptop
> does. GitHub Actions runs unattended but its scheduled jobs are best-effort and can be
> delayed under load, which adds jitter to `snapshot_ts`. A always-on machine is the
> safest if anyone has one.

### 1.2 Robustness (DONE)
- [x] Per-collector failure isolation in `main.py` — one source failing no longer stops
      the rest
- [x] Retry with backoff on transient HTTP failures, skipping retries on 401/403/404
      where retrying is pointless
- [x] Rotating file logging to `logs/` — stdout is lost under a scheduler
- [x] Failures logged with tracebacks, so gaps in the series are explainable later

### 1.3 Evaluate richer real-time sources — time-sensitive, high value
`GetPrediction` returns no train identifier, which is what makes arrival reconstruction
(Phase 2) hard and approximate. There are two better options, and **both must be
evaluated before collection starts**, because neither can be backfilled.

**a. GTFS-Realtime rail feeds.** The Mobility Database catalog lists three rail GTFS-RT
feeds alongside the static one:

| Feed | URL |
|---|---|
| Trip updates | `https://api.wmata.com/gtfs/rail-gtfsrt-tripupdates.pb` |
| Vehicle positions | `https://api.wmata.com/gtfs/rail-gtfsrt-vehiclepositions.pb` |
| Alerts | `https://api.wmata.com/gtfs/rail-gtfsrt-alerts.pb` |

This could **collapse most of Phase 2**. GTFS-RT `TripUpdates` are keyed by `trip_id`,
which joins directly to `stop_times.txt` — meaning observed and scheduled arrival come
from the same identifier and scheduled headway needs no inference at all. Supporting
evidence: `trips.txt` already carries `train_id` and `scheduled_trip_id` columns, so WMATA
is clearly tracking individual trains through the schedule.

- [ ] Fetch each feed and inspect it (needs `gtfs-realtime-bindings` + `protobuf`)
- [ ] Check whether `TripUpdates` carries actual arrival times or only predictions
- [ ] Confirm `trip_id` values match the static feed's
- [ ] **If this works, prefer it over countdown reconstruction** and rewrite Phase 2
      around it — reserve the prediction board as a fallback and cross-check

**b. The `TrainPositions` REST endpoint** — documented as including a train ID, track
circuit ID, line, direction, destination, and seconds-at-location.

- [ ] Run `python src/check_train_positions.py` once the key arrives
- [ ] If it carries a stable train ID, add a collector — useful for identity even if
      GTFS-RT covers arrivals

Collect whatever proves useful from day one, even before the processing code exists.
Reconstruction can be written later; the data to feed it only exists in real time.

### 1.4 Storage
- [x] Daily partitioning — every CSV collector writes `<name>_<YYYY-MM-DD>.csv`, and the
      GTFS-RT collector writes under `gtfs_rt/<feed>/<date>/`
- [x] GTFS-RT stored as gzipped raw protobuf: decoding is a schema assumption, and a
      wrong one loses data permanently, while raw bytes can be re-parsed any number of
      times
- [x] Raw data stays out of git
- [ ] **Measure actual growth after day one.** `GetPrediction/All` returns several
      hundred rows per call, so expect 400k–600k rows/day from predictions alone, plus
      the RT feeds. If it is heavier than expected, drop RT cadence or prune whichever
      real-time source Phase 1.3 rules out
- [ ] Exclude `data/` from OneDrive sync — per-minute appends in a synced folder cause
      sync churn and can lock files mid-write

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

> **Feed structure confirmed** against a mirrored copy of the rail feed
> (`reference/gtfs_notes.md`). Three things differ from the standard assumptions:
> there is **no `calendar.txt`** — only `calendar_dates.txt`, listing every service date
> explicitly; `departure_time` values **exceed 24:00:00** (observed up to `26:12:00`);
> and `route_id` is `RED`/`BLUE`/… while the prediction API uses `RD`/`BL`/….

- [x] Unzip and load `stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`,
      `calendar_dates.txt`
- [ ] Resolve the service calendar. Simpler than expected: with no `calendar.txt`, there
      are no weekly patterns to expand — map `service_id` to date directly from
      `calendar_dates.txt`
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

**Mostly solved** — `src/build_crosswalk.py` generates
`reference/station_crosswalk.csv` (125 rows) with validation that fails loudly rather
than dropping stops. Rebuild it whenever the GTFS feed is refreshed.

- [x] **Station.** `stop_times.txt` references *platform* ids, not station ids, and
      platforms encode the code cleanly as `PF_<LocationCode>_<1|2|C>`. Platforms are
      therefore the join target. This matters: station-level ids **combine** codes at the
      four transfer stations (`STN_A01_C01`, `STN_B01_F01`, `STN_D03_F03`, `STN_B06_E06`),
      so joining at station level would silently drop Metro Center, Gallery Place,
      L'Enfant Plaza and Fort Totten — four of the busiest in the system
- [x] **Line.** `RD`→`RED`, `BL`→`BLUE`, `GR`→`GREEN`, `YL`→`YELLOW`, `OR`→`ORANGE`,
      `SV`→`SILVER`, with the lines serving each platform derived from the schedule
      rather than assumed
- [x] **Shared platforms** handled — `lines_wmata` is multi-valued where several lines
      serve one platform (e.g. `PF_C01_C` → `BL;OR;SV`)
- [x] **Coverage validated** — every stop referenced by `stop_times.txt` resolves, no
      duplicate platform ids, no missing coordinates. 125 platforms / 102 location
      codes / 98 stations, matching WMATA's published counts
- [ ] **Direction — STILL OPEN, needs live data.** Platform suffix `1`/`2` is named
      "TRACK 1/2 PLATFORM" and very likely equals WMATA's `Group`, but this is a
      hypothesis, not a verified fact. **Validate against real predictions before
      trusting any headway** — a silent mismatch reverses direction for a whole line.
      Note that 79 of 102 codes have only a *center* platform serving both directions,
      so for those, direction must come from `direction_id`/destination, not the platform
- [ ] Re-run against the live feed once the API key arrives (see *Known limitation* below)

### 4.1 Station attributes (enables the "differs by station/line" analysis)
- [x] Station coordinates — in the crosswalk as `stop_lat`/`stop_lon`
- [ ] **Flag above-ground vs. underground segments.** This is likely the strongest
      predictor of weather sensitivity in the entire project: underground platforms are
      insulated from rain, snow, and heat, while above-ground track and rolling stock are
      not. Derive from WMATA station data or code manually — there are only 98 stations
- [x] Transfer stations flagged (`is_transfer_station`)
- [ ] Note terminals and single-track-prone segments

### Known limitation of the current crosswalk
It was built from a **mirrored GTFS snapshot dated 2024-10-01**, pulled from the
Mobility Database because the live feed needs an API key we did not have yet. The
*structure* is what matters here and is unlikely to have changed, but station codes,
platforms and schedules may have. **Re-run `src/build_crosswalk.py` against the live
feed as soon as the key arrives**, and diff the output before relying on it.

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
- [x] **Open-Meteo archive API confirmed working** (`archive-api.open-meteo.com/v1/archive`,
      free, no key). Hourly history for arbitrary coordinates and dates.
      **Weather is therefore a solved problem and off the risk list:** gaps in
      `collect_weather.py` do not matter, and per-station weather costs nothing but
      pipeline code. The live collector is kept as ground truth and because the archive
      lags by a few days
- [ ] Decide whether to use archive data as the primary weather source and demote the
      live collector to a cross-check
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
- [x] **Weather coverage audit — DONE, and it constrains the research question.**
      Open-Meteo archive data for Metro Center, 20 Oct – 15 Dec, 2019–2025:

      | Condition | median hours | range |
      |---|---|---|
      | Rain | 121 | 100–218 |
      | Heavy rain (≥2.5 mm/h) | 18 | 14–52 |
      | **Snow** | **4** | **2–19** |
      | Freezing (≤0 °C) | 84 | 53–189 |
      | Gusts ≥40 km/h | 147 | 92–214 |

      Out of 1,368 hours. **Snow is not testable in this window** — a median of 4 hours
      cannot support any claim, and the proposal names snow first among the conditions
      investigated. Rain, wind and freezing temperatures are all well-powered. Reframe
      the question around those three, and state the snow limitation explicitly in the
      report rather than reporting a null result as if it were a finding.
- [ ] Re-run the same audit against the *actual* collection window once it closes, since
      a single season can deviate from the climatology in either direction
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
| 1 | Phase 1 — **start collecting** | API key | Code ready; run it the day the key lands |
| 2 | Phase 1.3 — settle the arrival source | 1 day of data | Decides whether Phase 2 is hard or easy |
| 3 | Phase 3 — GTFS parsing | GTFS zip only | Can start now; structure already mapped |
| 4 | Phase 4.1 — above/underground | nothing | Manual; start any time |
| 5 | Phase 2 — arrival reconstruction | Phase 1.3 outcome | Longest and riskiest |
| 6 | Phases 5 + 6 — weather and incidents | Phase 2 output | Parallelizable |
| 7 | Phase 7 — analytical dataset | Phases 2–6 | |
| 8 | Phase 8 — validation | Phase 7 | Gate before analysis |
| 9 | Phases 9 + 10 — EDA and analysis | Phase 8 | |
| 10 | Phase 11 — deliverables | All | |

Good parallel split across three people: one owns collection infrastructure (Phase 1),
one owns GTFS parsing and the crosswalk (Phases 3–4), one owns reconstruction (Phase 2).
The phases converge at Phase 7.

---

## Risk register

Carried from the proposal, updated with current status and mitigation.

| Risk | Status | Mitigation |
|---|---|---|
| Collection not yet running — data lost permanently | **Open, urgent** | Code is ready; blocked only on the API key. Start the day it arrives |
| Arrival reconstruction proves unreliable | **Open, high** | GTFS-RT may remove the problem entirely (Phase 1.3); careful Phase 2 validation either way |
| **No testable snow in the collection window** | **Confirmed** | Climatology measured (Phase 9): median 4 snow hours. Reframe around rain/wind/freezing and state the limitation |
| Rate limits / key expiry | Mitigated | ~7,500 of 50,000 daily calls; retries skip non-transient errors; failures logged |
| Missed snapshots between arrivals | Expected | 60s cadence; flag gap-spanning headways (Phase 2.1) |
| Timestamp / identifier misalignment | **Partly closed** | Crosswalk built and validated (Phase 4); `Group` ↔ direction still unverified; UTC throughout, DST-safe conversion still to do |
| Weather granularity — one point for the system | **Closed** | Archive API confirmed: any coordinates, any past date, free (Phase 5) |
| Confounding non-weather incidents | **Open** | Phase 6 controls, separating weather-caused incidents |
| Raw data volume | **Partly closed** | Daily partitioning and gzipped protobuf in place; measure actual growth after day one |
| Crosswalk built from a stale 2024 feed | **Open** | Re-run `build_crosswalk.py` on the live feed and diff (Phase 4) |
