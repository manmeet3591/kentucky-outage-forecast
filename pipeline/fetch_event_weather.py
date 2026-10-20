"""Hourly event weather at sample points in every county.

- "analysis": ERA5 reanalysis (what actually happened, best estimate)
- "lead1".."lead3": NOAA GFS forecasts issued 1-3 days before each valid hour
  (Open-Meteo Previous Runs API), i.e. what a forecaster would have seen in advance.
"""
import json
import pathlib
import time

import requests

from geo import CountyIndex, centroid

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
EVENT = json.loads((ROOT / "pipeline" / "event.json").read_text())
LEADS = [1, 2, 3]
BATCH = 40


def sample_points():
    counties = json.loads((RAW / "counties.geojson").read_text())["features"]
    cidx = CountyIndex(counties)
    pts = []
    for c in json.loads((RAW / "risk_grid.json").read_text()):
        pts.append({"county": c["county"], "lon": c["lon"], "lat": c["lat"]})
    for f in counties:  # centroid of every county, so small counties are always sampled
        lon, lat = centroid(f["geometry"])
        if cidx.find(lon, lat) is None:  # odd shapes: fall back to first vertex inside
            continue
        pts.append({"county": f["properties"]["name"], "lon": round(lon, 3), "lat": round(lat, 3)})
    return pts


def get(url, params, tries=5):
    for i in range(tries):
        r = requests.get(url, params=params, timeout=120)
        if r.status_code == 200:
            return r.json()
        print(f"  HTTP {r.status_code}: {r.text[:120]}")
        time.sleep(30 * (i + 1))
    raise RuntimeError(url)


def main():
    pts = sample_points()
    print(f"{len(pts)} sample points")
    out = {"time": None, "points": pts, "analysis": {"rain": [], "gust": []},
           **{f"lead{d}": {"rain": [], "gust": []} for d in LEADS}}
    for i in range(0, len(pts), BATCH):
        b = pts[i:i + BATCH]
        common = {"latitude": ",".join(str(p["lat"]) for p in b), "longitude": ",".join(str(p["lon"]) for p in b),
                  "start_date": EVENT["start"], "end_date": EVENT["end"], "timezone": "Africa/Nairobi"}
        era = get("https://archive-api.open-meteo.com/v1/archive",
                  {**common, "hourly": "precipitation,wind_gusts_10m", "models": "era5"})
        era = era if isinstance(era, list) else [era]
        hourly = ",".join(f"precipitation_previous_day{d},wind_gusts_10m_previous_day{d}" for d in LEADS)
        fc = get("https://previous-runs-api.open-meteo.com/v1/forecast",
                 {**common, "hourly": hourly, "models": "gfs_seamless"})
        fc = fc if isinstance(fc, list) else [fc]
        for e, f in zip(era, fc):
            out["time"] = out["time"] or e["hourly"]["time"]
            out["analysis"]["rain"].append(e["hourly"]["precipitation"])
            out["analysis"]["gust"].append(e["hourly"]["wind_gusts_10m"])
            for d in LEADS:
                out[f"lead{d}"]["rain"].append(f["hourly"][f"precipitation_previous_day{d}"])
                out[f"lead{d}"]["gust"].append(f["hourly"][f"wind_gusts_10m_previous_day{d}"])
        print(f"points {i + len(b)}/{len(pts)}")
        time.sleep(8)
    (RAW / "event_weather.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main()
