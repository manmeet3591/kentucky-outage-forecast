"""Shared loading: event weather grouped by county, and EAGLE-I observed outages on the same clock."""
import csv
import datetime as dt
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
STEP = 3  # hours per output step


def load_events():
    return json.loads((ROOT / "pipeline" / "events.json").read_text())


def load_counties():
    g = json.loads((RAW / "counties.geojson").read_text())
    return g, {f["properties"]["name"]: f["properties"] for f in g["features"]}


def county_points(ev, src):
    """-> times, {county: [{'rain': [...], 'gust': [...]}, ...]}"""
    wx = json.loads((RAW / f"weather_{ev['id']}.json").read_text())
    by = {}
    for i, p in enumerate(wx["points"]):
        by.setdefault(p["county"], []).append({"rain": wx[src]["rain"][i], "gust": wx[src]["gust"][i]})
    return wx["time"], by


def observed(ev, times, counties):
    """EAGLE-I customers out per county, hourly (mean of 15-min snapshots; missing snapshot = 0)."""
    fips2name = {p["fips"]: n for n, p in counties.items()}
    t0 = dt.datetime.fromisoformat(times[0])
    n = len(times)
    acc = {name: [[0.0, 0] for _ in range(n)] for name in counties}
    snaps = [set() for _ in range(n)]
    years = sorted({ev["start"][:4], ev["end"][:4]})
    for y in years:
        with open(RAW / f"eaglei_ky_{y}.csv") as f:
            for row in csv.reader(f):  # 2024+ files add a total_customers column
                fips, val, ts = row[0], row[3], row[4]
                t = dt.datetime.fromisoformat(ts)
                h = int((t - t0).total_seconds() // 3600)
                if 0 <= h < n and fips in fips2name:
                    acc[fips2name[fips]][h][0] += float(val or 0)
                    snaps[h].add(ts)
    out = {}
    for name, rows in acc.items():
        out[name] = [s / max(1, len(snaps[h])) for h, (s, _) in enumerate(rows)]
    return out


def down(xs, how="mean"):
    out = []
    for i in range(0, len(xs), STEP):
        c = xs[i:i + STEP]
        out.append(sum(c) / len(c) if how == "mean" else max(c) if how == "max" else sum(c))
    return out
