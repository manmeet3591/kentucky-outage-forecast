# Kentucky Power Outage & Restoration Forecast

Weather-driven forecasts of **which Kentucky counties will lose power, when, and for how long**, calibrated and tested against observed outages from ORNL's **EAGLE-I**.

**Live dashboard:** https://manmeet3591.github.io/kentucky-outage-forecast/

A Disaster Science Operations Center prototype.

## Events

The **24 events** are the largest Kentucky outage events in EAGLE-I for 2018–2025 (`pipeline/find_events.py`: statewide customers out, 3-hour running median, peaks at least 5 days apart).

- **22 calibration events** (ERA5 only). The March 2023 windstorm (~520k out) plus 21 wind and rain events with 30k–170k out: 10 synoptic windstorms, cold fronts or flood events, and 11 thunderstorm or tornado days.
- **2 independent tests** with 1–3 day GFS forecasts:
  - Memorial Day weekend storms (24–31 May 2024): ~209k out.
  - Remnants of Hurricane Helene (25 Sep – 2 Oct 2024): ~220k out.
- **Excluded:**
  - Ice and snow storms: Feb 2021, Nov 2018, Jan 2025.
  - The December 2022 Elliott cold wave and TVA rolling blackouts.
  - Three one-hour reporting glitches in Jefferson and Fayette counties: 2019-09-13, 2020-10-12, 2025-11-12. The last one shows as a 469k-customer "peak".

## Results vs EAGLE-I

Hindcast (ERA5) skill on the test events, single-event fit (March 2023 only) vs the 22-event fit:

| Test event | Metric | Single-event fit | 22-event fit |
|---|---|---|---|
| Helene | Peak vs observed | 209% | **142%** |
| Helene | Customer-hours vs observed | 456% | **70%** |
| Helene | Time to 90% restored (observed 63 h) | beyond the event window | 21 h |
| Helene | Statewide curve correlation | 0.88 | 0.77 |
| Helene | Hard-hit counties caught / false alarm ratio | 100% / 43% | 100% / 43% |
| May 2024 | Peak vs observed | 4% | 7% |
| May 2024 | Statewide curve correlation | 0.82 | 0.77 |

GFS forecasts for Helene, peak vs observed:

| Lead | Single-event fit | 22-event fit |
|---|---|---|
| 1 day | 339% | 233% |
| 2 days | 146% | 106% |
| 3 days | 52% | 46% |

With the 22-event fit, the 3-day forecast put the statewide peak in the same 3-hour step as observed, and 2 days ahead 97% of hard-hit counties were flagged.

What changed:

- **Better:** Helene's overprediction is much smaller, in both peak and customer-hours.
- **Worse:**
  - Restoration is now too fast. The fitted τ₀ is 3 h, so outages clear almost as soon as the wind drops.
  - The March 2023 fit got worse: peak 113% → 77%, curve correlation 0.98 → 0.46.
- **Still missed:** the May 2024 thunderstorms (7%), as expected at ~25 km.

Across calibration events the hindcast peak ratio runs from 3% to 945% (median 83%). On 25 km weather, peak gust alone can't separate events:

- March 2019 and January 2020 reached ERA5 gusts of 120 km/h but only ~40k customers lost power.
- March 2023 reached 140 km/h and ~520k lost power.
- Thunderstorm days barely register at 45–72 km/h.

The fit also sent the crew stand-down gust (90 km/h) and the flood slow-down (400 mm) to the edge of their grids, so both are effectively off.

The full tables are in the dashboard's *Skill vs EAGLE-I* tab.

### Versions tried, and what the test events influenced

The model form changed several times during this work. Below is every version, how the final one was picked, and where I saw test-event scores along the way.

| # | Loss (and model change) | Fit result | Why dropped / kept |
|---|---|---|---|
| v1 | Normalised county-hour MSE, mean over events | Best loss 1.13, worse than predicting zero | Dropped: underprediction is capped at 1 but overprediction is unbounded, so the fit collapses to "predict nothing" |
| v2 | ln² statewide peak ratio + ln² customer-hours ratio | 125 km/h, β 0.4, τ₀ 3 h | **Selected** by leave-one-event-out |
| v3 | ln² peak + MSE of the peak-normalised statewide curve | τ₀ 2 h | Leave-one-out worse |
| v4 | v3 + crew saturation, τ × (1 + U<sub>max</sub>/TAU_LOAD) | TAU_LOAD fitted to off | Leave-one-out worse (same as v3) |
| v5 | ln² peak + MSE of the peak-aligned, peak-normalised 96 h restoration curve, with crew saturation | τ₀ 2 h, TAU_LOAD off | Leave-one-out worse |

**How v2 was selected.** I compared v2–v5 by leave-one-event-out over the 22 calibration events only (`pipeline/compare_versions.py` → `pipeline/version_comparison.json`; test events are never loaded):

- For each held-out event, each version's restoration settings were refitted on the other 21 events with that version's own loss.
- Every version was then scored on the held-out event with the same metrics.

Held-out time to 90% restored, typical (median) error factor:

| Version | Error factor |
|---|---|
| v2 | 1.9× |
| v3, v4 | 3.7× |
| v5 | 3.7× |

Held-out restoration-curve MSE:

| Version | MSE |
|---|---|
| v2 | 0.033 |
| v3, v4 | 0.039 |
| v5 | 0.039 |

**Where test scores were seen** (stated plainly, as test-set exposure):

- **While diagnosing v1:** I printed per-event errors with Helene and May 2024 included.
- **After v2:**
  - I compared v2 on all 22 events against a 10-event synoptic-only fit, and printed Helene's peak ratio for both: 1.52 vs 0.66.
  - I kept "all events" because the task called for it, not because of that number, but I saw it.
  - The synoptic-only fit was not pursued.
- **Before adding crew saturation (v4):**
  - A diagnostic printed restoration times for every event, tests included.
  - Helene restoring in ~21 h against 63 h observed was part of the motivation for crew saturation. So was the calibration events' pattern: big storms take 85–90 h, most others 15–45 h.
- **While moving to v5:**
  - A diagnostic table showed Helene's restoration-curve error next to the calibration average.
  - The move was justified by the calibration average, but the Helene numbers were in view.
- **Why this doesn't change the outcome:** test scores shaped which variants I *tried*. They did not pick the final version. The calibration-only leave-one-out picked v2, the simplest variant, which existed before any test-informed change. The test numbers above are still not a clean blind test, and should be read that way.

## Going beyond EAGLE-I

EAGLE-I shows who is out *now*. This system predicts who **will** be out (1–3 days ahead today), how long restoration will take, what is driving each outage, and how many hospitals are likely on backup power. EAGLE-I's 2014–2025 archive is its training and verification ground truth.

## Model

`pipeline/outage_model.py`:

```
D   = 1 - (1 - F_gust)(1 - F_rain24)(1 - F_rain72)    lognormal fragility per sample point (288 points)
U_t = max(mean_3h(D), U_{t-1} - restored)              share of customers out, per county
restored = U (1 - e^{-1/tau}),  tau = tau0 (1 + R72/TAU_RAIN),  paused while gust > SAFE_GUST or rain > 8 mm/h
```

`pipeline/calibrate.py` fits the gust fragility (median 125 km/h, β 0.4), τ₀ (3 h), the crew stand-down gust and the flood slow-down jointly on all 22 calibration events, with a coordinate-descent grid search. Each event weighs the same.

The loss is the squared log error of the statewide peak plus that of customer-hours, with a 10,000-customer floor. It is symmetric, so 2× over costs the same as 2× under. Test events are never loaded.

The model also has an optional crew-saturation term (TAU_LOAD). It is off by default because it wasn't selected.

## Data

| | Source |
|---|---|
| Observed outages, customer counts | EAGLE-I recorded outages 2014–2025 and modeled customer counts (Brelsford et al., ORNL, figshare) |
| Hindcast weather | ERA5 hourly via Open-Meteo |
| Forecast weather | NOAA GFS, runs issued 1–3 days before valid time, via Open-Meteo Previous Runs API (archive from early 2024) |
| Counties | US Census TIGERweb |
| Hospitals, substations | OpenStreetMap contributors (ODbL) |

## Rebuild

Pure Python 3 with `requests`.

```bash
cd pipeline
python3 fetch_static.py              # counties, customers, OSM assets
python3 fetch_eaglei.py 2018 2019 2020 2021 2022 2023 2024 2025   # streams ~9 GB, keeps Kentucky rows
python3 find_events.py 2018 2019 2020 2021 2022 2023 2024 2025    # rank statewide outage peaks
python3 fetch_event_weather.py       # ERA5 (+ GFS for 2024 tests) for events.json; Open-Meteo rate-limits, rerun to resume
python3 calibrate.py                 # -> params.json (~20 min)
python3 compare_versions.py          # optional: leave-one-event-out version comparison (~10 min)
python3 build.py                     # -> docs/data/
python3 -m http.server -d ../docs 8000
```

Add events in `pipeline/events.json`.

## Roadmap

1. Move from one set of fragility curves to a learned model. Its features would be gust exposure area and duration, vegetation, terrain, feeder exposure and utility territory, trained on the 2014–2025 EAGLE-I events. Restoration needs its own model: the current one can't fit both 20 h and 90 h recoveries.
2. Use HRRR (3 km) and Aircast SR (1 km, 1 h) inputs for thunderstorm events.
3. Live mode: daily runs on the latest forecasts, with alerts for county emergency managers and utility control rooms (EKPC, Big Rivers, LG&E/KU).
4. Add ice storms, and link to load forecasting for extreme heat and cold swings.
