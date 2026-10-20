# Kenya Power Outage & Restoration Forecast

Weather-driven forecasts of **who will lose power, when, and for how long**. The first case is a hindcast of Kenya's **April–May 2024 long-rains floods and Cyclone Hidaya** (15 April – 10 May 2024).

**Live dashboard:** https://manmeet3591.github.io/kenya-outage-forecast/

A Disaster Science Operations Center prototype. Companion to the [Kenya Critical Infrastructure Risk map](https://github.com/manmeet3591/kenya-infra-risk).

## Why: going beyond EAGLE-I

ORNL's EAGLE-I monitors US outages from utility feeds and shows who is out *now*. This system targets decisions made *before* and *during* an event:

- **Lead time.** The same model runs on NOAA GFS forecasts issued 1, 2 and 3 days ahead, so you can see what a control room would have known in advance.
- **Restoration.** It predicts time to 90% restoration, including slowdowns from flooding and crew stand-downs in high wind or heavy rain.
- **Drivers.** Every predicted outage is attributed to gusts, intense rain or prolonged flooding.
- **Critical facilities.** It estimates how many hospitals are likely to be running on backup power.
- **No outage feed needed.** It runs on weather and asset data alone; utility logs make it better.

## Dashboard

- A timeline player with a county map of the predicted share of people without power, with hospitals flagged in affected counties.
- A switch between **Hindcast (ERA5)** and **Forecast 1 / 2 / 3 days ahead**.
- A national curve of people without power for all four inputs, plus event annotations.
- A county panel: outage curves, rain and gust drivers, peak, restoration time and people-hours.
- **Forecast skill**: forecast versus hindcast consistency (hit rate, false alarms, timing error).

## Model

`pipeline/outage_model.py` is a transparent fragility-and-restoration model:

```
D   = 1 - (1 - F_gust)(1 - F_rain24)(1 - F_rain72)    lognormal fragility curves per sample point
U_t = max(mean_6h(D), U_{t-1} - restored)              share of people without power
restored = U (1 - e^{-1/tau}),  tau = tau0 (1 + R72 / 80 mm),  paused in unsafe weather
```

The parameters are **priors**. The plan is to calibrate them, then replace them with a learned model (gradient boosting, or a graph neural network over the feeder network), once KPLC interruption logs are available.

## Key findings from the hindcast

- The national peak is about 0.9 million people without power, on 2 May 2024. The heaviest hits are Mt Kenya slopes (Meru) and the coast (Mombasa, Kilifi, Kwale) as Hidaya approached.
- GFS forecasts caught about half of the flagged counties 1–2 days ahead. Timing and location skill is limited at ~25 km resolution.
- **Nairobi is a known miss.** ERA5's wettest 3-hour county rainfall is only 12.6 mm, even though there was severe flash flooding. Coarse models smooth out intense urban storms. This motivates the **1 km Aircast SR** model.

These are consistency checks against a reanalysis-driven hindcast, **not validation against observed outages**.

## Data

| | Source |
|---|---|
| Hindcast weather | ERA5 hourly (Copernicus/ECMWF) via Open-Meteo |
| Forecast weather | NOAA GFS, previous runs 1–3 days before valid time, via Open-Meteo Previous Runs API |
| Counties | geoBoundaries gbOpen KEN ADM1 (CC BY 4.0) |
| Hospitals, substations | OpenStreetMap contributors (ODbL) |
| Population | KNBS 2019 census (via Wikipedia "Counties of Kenya") |

## Rebuild

Pure Python 3 with `requests`. The counties, assets and grid inputs in `raw/` come from the `kenya-infra-risk` pipeline.

```bash
cd pipeline
python3 fetch_population.py
python3 fetch_event_weather.py   # ~2 min
python3 build_outage.py          # -> docs/data/
python3 -m http.server -d ../docs 8000
```

To run a different event, edit `pipeline/event.json` (dates, notes). Check that the Previous Runs API covers your dates.

## Roadmap

1. Calibrate against KPLC interruption records, and social-media and news outage reports, as interim validation.
2. Swap ERA5/GFS for **Aircast SR** (1 km, 1 h), and extend lead time with the AI S2S model.
3. Feeder-level exposure: vegetation, terrain and line age from OSM and utility GIS.
4. Live mode: run daily on the latest forecasts and push alerts to county emergency managers.
