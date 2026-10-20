"""Hourly event weather at sample points across Kentucky, per event in events.json.

- "analysis": ERA5 reanalysis (what actually happened, best estimate)
- "lead1".."lead3": NOAA GFS forecasts issued 1-3 days before each valid hour (Open-Meteo
  Previous Runs API; archive starts in early 2024, so only for events with "forecasts": true)
All times UTC.
"""
import json
import pathlib
import sys
import time

import requests

from geo import CountyIndex, centroid

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
EVENTS = json.loads((ROOT / "pipeline" / "events.json").read_text())
LEADS = [1, 2, 3]
BATCH = 50
GRID = 0.25  # deg, ERA5 native


def sample_points():
    counties = json.loads((RAW / "counties.geojson").read_text())["features"]
    cidx = CountyIndex(counties)
    pts = []
    lat = 36.5
    while lat <= 39.15:
        lon = -89.5
        while lon <= -81.95:
            c = cidx.find(lon, lat)
            if c:
                pts.append({"county": c["properties"]["name"], "lon": round(lon, 3), "lat": round(lat, 3)})
            lon += GRID
        lat += GRID
    for f in counties:
        lon, lat = centroid(f["geometry"])
        pts.append({"county": f["properties"]["name"], "lon": round(lon, 3), "lat": round(lat, 3)})
    return pts


def get(url, params, tries=5):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=120)
            if r.status_code == 200:
                d = r.json()
                return d if isinstance(d, list) else [d]
            print(f"  HTTP {r.status_code}: {r.text[:150]}")
        except requests.RequestException as e:
            print(f"  {e}")
        time.sleep(30 * (i + 1))
    raise RuntimeError(url)


def fetch(ev, pts):
    out_path = RAW / f"weather_{ev['id']}.json"
    if out_path.exists():
        print(f"{ev['id']}: cached")
        return
    srcs = ["analysis"] + ([f"lead{d}" for d in LEADS] if ev["forecasts"] else [])
    out = {"time": None, "points": pts, **{s: {"rain": [], "gust": []} for s in srcs}}
    for i in range(0, len(pts), BATCH):
        b = pts[i:i + BATCH]
        common = {"latitude": ",".join(str(p["lat"]) for p in b), "longitude": ",".join(str(p["lon"]) for p in b),
                  "start_date": ev["start"], "end_date": ev["end"], "timezone": "GMT"}
        era = get("https://archive-api.open-meteo.com/v1/archive",
                  {**common, "hourly": "precipitation,wind_gusts_10m", "models": "era5"})
        for e in era:
            out["time"] = out["time"] or e["hourly"]["time"]
            out["analysis"]["rain"].append(e["hourly"]["precipitation"])
            out["analysis"]["gust"].append(e["hourly"]["wind_gusts_10m"])
        if ev["forecasts"]:
            hourly = ",".join(f"precipitation_previous_day{d},wind_gusts_10m_previous_day{d}" for d in LEADS)
            for f in get("https://previous-runs-api.open-meteo.com/v1/forecast",
                         {**common, "hourly": hourly, "models": "gfs_seamless"}):
                for d in LEADS:
                    out[f"lead{d}"]["rain"].append(f["hourly"][f"precipitation_previous_day{d}"])
                    out[f"lead{d}"]["gust"].append(f["hourly"][f"wind_gusts_10m_previous_day{d}"])
        print(f"{ev['id']}: points {i + len(b)}/{len(pts)}")
        time.sleep(6)
    out_path.write_text(json.dumps(out))


def main():
    pts = sample_points()
    print(f"{len(pts)} sample points")
    only = sys.argv[1:]
    for ev in EVENTS:
        if not only or ev["id"] in only:
            fetch(ev, pts)


if __name__ == "__main__":
    main()
