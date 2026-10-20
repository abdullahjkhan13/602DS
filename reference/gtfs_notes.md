# WMATA Rail GTFS — structure notes

Findings from inspecting the rail feed. Recorded so the next person does not have to
rediscover them. Source for these notes: a mirrored snapshot dated **2024-10-01**
(Mobility Database source `1847`), used because the live feed requires an API key.
Re-verify against the live feed once available.

## Files present

`agency.txt`, `calendar_dates.txt`, `routes.txt`, `shapes.txt`, `stop_times.txt`,
`stops.txt`, `trips.txt`, `feed_info.txt`, `levels.txt`, `pathways.txt`

**There is no `calendar.txt`.** Service is defined entirely by `calendar_dates.txt`,
which lists every service date explicitly (117 rows / 9 `service_id`s in the snapshot).
This is simpler than the usual pattern — there are no weekly patterns to expand, just a
direct `service_id` → date mapping.

## Stop hierarchy

`stops.txt` has 2,050 rows across four `location_type` values:

| `location_type` | meaning | count |
|---|---|---|
| 1 | station | 98 |
| 0 | platform | 125 |
| 2 | entrance | 235 |
| 3 | generic node | 1,592 |

**`stop_times.txt` references platforms (`PF_…`), never stations.** Platforms are
therefore the join target for scheduled arrival times.

### Platform ids encode the WMATA LocationCode

Format: `PF_<LocationCode>_<1|2|C>`

- `_1` / `_2` — side platforms, named "TRACK 1/2 PLATFORM" (23 codes each)
- `_C` — center platform serving both directions (79 codes)

All 125 platform ids parse; they cover 102 distinct LocationCodes.

### Station ids combine codes at transfer stations

Four stations serve two LocationCodes each and use a **combined** `stop_id`:

| `stop_id` | Station | Codes |
|---|---|---|
| `STN_A01_C01` | Metro Center | A01, C01 |
| `STN_B01_F01` | Gallery Place | B01, F01 |
| `STN_D03_F03` | L'Enfant Plaza | D03, F03 |
| `STN_B06_E06` | Fort Totten | B06, E06 |

This is the trap in the crosswalk: stripping `STN_` yields `A01_C01`, which matches no
WMATA LocationCode, so a naive station-level join silently drops four of the busiest
stations in the system. Joining at the **platform** level avoids the problem entirely,
since platform ids carry a single code.

98 stations × (4 with two codes) = 102 LocationCodes, matching WMATA's published counts.

## Routes

`route_id` is the full colour name, not the two-letter code the prediction API uses:

| GTFS `route_id` | API `Line` |
|---|---|
| `RED` | `RD` |
| `BLUE` | `BL` |
| `GREEN` | `GR` |
| `YELLOW` | `YL` |
| `ORANGE` | `OR` |
| `SILVER` | `SV` |

## Times past midnight

`departure_time` exceeds 24 hours — `26:12:00` appears in the snapshot, meaning 02:12 on
the following day. `pd.to_datetime` will fail or mangle these. Parse as a timedelta from
the service date instead.

## Fields worth noting

`trips.txt` carries `train_id` and `scheduled_trip_id` in addition to `trip_id`. WMATA is
evidently tracking individual trains against the schedule, which is promising for linking
the static feed to real-time data (see ROADMAP Phase 1.3).

## Open question

Does platform suffix `1`/`2` correspond to the prediction API's `Group` field (`1`/`2`)?
The naming strongly suggests yes, but **this is unverified** and cannot be checked without
live prediction data. It matters: getting it backwards reverses direction for an entire
line. Note also that 79 of 102 codes have only a center platform, so for those, direction
must come from `direction_id` or destination rather than the platform id.
