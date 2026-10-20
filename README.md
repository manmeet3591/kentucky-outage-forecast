# Kentucky Power Outage & Restoration Forecast

Weather-driven forecasts of **which Kentucky counties will lose power, when, and for how long**, calibrated and tested against observed outages from ORNL's **EAGLE-I**.

**Live dashboard:** https://manmeet3591.github.io/kentucky-outage-forecast/

A Disaster Science Operations Center prototype.

## Events

| Event | Role | EAGLE-I observed peak |
|---|---|---|
| March 2023 windstorm (1–9 Mar) | calibration | ~523k customers out (≈ 22% of Kentucky) |
| Memorial Day weekend storms (24–31 May 2024) | independent test, with 1–3 day forecasts | ~209k |
| Remnants of Hurricane Helene (25 Sep – 2 Oct 2024) | independent test, with 1–3 day forecasts | ~220k |

## Results vs EAGLE-I

- **Calibration (March 2023):** statewide peak within 13%, peak timing exact, statewide curve correlation 0.98.
- **Helene (test):** in forecasts issued **3 days ahead**, the statewide peak arrived within 3 h of the observed peak, and 97% of hard-hit counties (≥5% out) were flagged 2 days ahead. Magnitude was overpredicted (hindcast about 2× the observed peak) and restoration was too slow. One calibration event isn't enough.
- **Memorial Day storms (test): missed.** Thunderstorm gusts aren't resolved by ~25 km ERA5/GFS, so the hindcast reached only 4% of the observed peak. This is the case for 3 km HRRR and **1 km Aircast SR** inputs.

The full tables are in the dashboard's *Skill vs EAGLE-I* tab.

## Going beyond EAGLE-I

EAGLE-I shows who is out *now*. This system predicts who **will** be out (1–3 days ahead today), how long restoration will take, what is driving each outage, and how many hospitals are likely on backup power. EAGLE-I's 2014–2025 archive is its training and verification ground truth.

## Model

`pipeline/outage_model.py`:

```
D   = 1 - (1 - F_gust)(1 - F_rain24)(1 - F_rain72)    lognormal fragility per sample point (288 points)
U_t = max(mean_3h(D), U_{t-1} - restored)              share of customers out, per county
restored = U (1 - e^{-1/tau}),  tau = tau0 (1 + R72/80 mm),  paused while gust > 65 km/h or rain > 8 mm/h
```

`pipeline/calibrate.py` fits the gust fragility (median 110 km/h, β 0.3) and τ₀ (36 h) by grid search on March 2023 only. The loss is the RMSE of customers out per county-hour against EAGLE-I.

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
python3 fetch_eaglei.py 2023 2024    # streams ~2.6 GB, keeps Kentucky rows
python3 fetch_event_weather.py       # ERA5 + GFS for events.json
python3 calibrate.py                 # -> params.json
python3 build.py                     # -> docs/data/
python3 -m http.server -d ../docs 8000
```

Add events in `pipeline/events.json`.

## Roadmap

1. Calibrate across dozens of EAGLE-I events from 2014–2025, then move to a learned model with vegetation, terrain, feeder and utility-territory features.
2. Use HRRR (3 km) and Aircast SR (1 km, 1 h) inputs for thunderstorm events.
3. Live mode: daily runs on the latest forecasts, with alerts for county emergency managers and utility control rooms (EKPC, Big Rivers, LG&E/KU).
4. Add ice storms, and link to load forecasting for extreme heat and cold swings.
