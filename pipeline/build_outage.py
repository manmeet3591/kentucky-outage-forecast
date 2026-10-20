"""Run the outage model for the event (ERA5 analysis + GFS 1-3 day lead forecasts) -> docs/data/."""
import json
import math
import pathlib

from outage_model import PARAMS, simulate, summarize

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "raw", ROOT / "docs" / "data"
SOURCES = ["analysis", "lead1", "lead2", "lead3"]
STEP = 3  # hours per output step
FLAG = 0.05  # county counted as "significant outage" at >= 5% of people out


def down(xs, how="mean"):
    out = []
    for i in range(0, len(xs), STEP):
        chunk = xs[i:i + STEP]
        out.append(sum(chunk) / len(chunk) if how == "mean" else max(chunk) if how == "max" else sum(chunk))
    return out


def pearson(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wx = json.loads((RAW / "event_weather.json").read_text())
    pop = json.loads((RAW / "population.json").read_text())
    event = json.loads((ROOT / "pipeline" / "event.json").read_text())
    counties = json.loads((RAW / "counties.geojson").read_text())
    assets = json.loads((RAW / "assets.geojson").read_text())["features"]
    times = wx["time"]
    names = [f["properties"]["name"] for f in counties["features"]]

    hospitals = {n: 0 for n in names}
    substations = {n: 0 for n in names}
    for a in assets:
        p = a["properties"]
        if p["cat"] == "hospital":
            hospitals[p["county"]] = hospitals.get(p["county"], 0) + 1
        elif p["cat"] == "substation":
            substations[p["county"]] = substations.get(p["county"], 0) + 1

    series, summary = {}, {}
    for src in SOURCES:
        series[src], summary[src] = {}, {}
        for name in names:
            idx = [i for i, pt in enumerate(wx["points"]) if pt["county"] == name]
            pts = [{"rain": wx[src]["rain"][i], "gust": wx[src]["gust"][i]} for i in idx]
            sim = simulate(pts)
            s = summarize(sim["U"], times)
            s["people_peak"] = round(s["peak"] * pop[name])
            s["people_hours"] = round(s["outage_hours"] * pop[name])
            s["hospitals_peak"] = round(s["peak"] * hospitals[name], 1)
            summary[src][name] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}
            series[src][name] = {
                "out": [round(x, 4) for x in down(sim["U"])],
                "rain": [round(x, 1) for x in down([r or 0 for r in [sum((pt["rain"][t] or 0) for pt in pts) / len(pts) for t in range(len(times))]], "sum")],
                "gust": [round(x) for x in down([max((pt["gust"][t] or 0) for pt in pts) for t in range(len(times))], "max")],
            }
        print(src, "national peak people out:",
              max(sum(series[src][n]["out"][k] * pop[n] for n in names) for k in range(len(times) // STEP)))

    national = {src: [round(sum(series[src][n]["out"][k] * pop[n] for n in names))
                      for k in range(len(series[src][names[0]]["out"]))] for src in SOURCES}

    # forecast consistency vs the analysis-driven hindcast (not validation against observed outages)
    skill = {}
    a = summary["analysis"]
    for src in SOURCES[1:]:
        f = summary[src]
        flagged_a = {n for n in names if a[n]["peak"] >= FLAG}
        flagged_f = {n for n in names if f[n]["peak"] >= FLAG}
        hits = flagged_a & flagged_f
        timing = [abs((int(f[n]["peak_time"][8:10]) * 24 + int(f[n]["peak_time"][11:13])) -
                      (int(a[n]["peak_time"][8:10]) * 24 + int(a[n]["peak_time"][11:13])))
                  for n in hits if f[n]["peak_time"][5:7] == a[n]["peak_time"][5:7]]
        skill[src] = {
            "corr_peak": round(pearson([a[n]["peak"] for n in names], [f[n]["peak"] for n in names]) or 0, 3),
            "hit_rate": round(len(hits) / len(flagged_a), 3) if flagged_a else None,
            "false_alarm_ratio": round(len(flagged_f - flagged_a) / len(flagged_f), 3) if flagged_f else None,
            "n_flagged_analysis": len(flagged_a), "n_flagged_forecast": len(flagged_f),
            "median_peak_timing_error_h": sorted(timing)[len(timing) // 2] if timing else None,
            "national_peak_ratio": round(max(national[src]) / max(national["analysis"]), 3) if max(national["analysis"]) else None,
        }
        print(src, skill[src])

    for f in counties["features"]:
        n = f["properties"]["name"]
        f["properties"].update({"pop": pop[n], "hospitals": hospitals[n], "substations": substations[n]})

    def dump(name, obj):
        (OUT / name).write_text(json.dumps(obj, separators=(",", ":")))

    dump("counties.geojson", counties)
    dump("series.json", series)
    dump("hospitals.geojson", {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": a["geometry"], "properties": {"name": a["properties"].get("name"), "county": a["properties"]["county"]}}
        for a in assets if a["properties"]["cat"] == "hospital"]})
    dump("event.json", {**event, "times": times[::STEP], "step_h": STEP, "sources": SOURCES, "summary": summary,
                        "national": national, "skill": skill, "flag": FLAG, "params": PARAMS,
                        "total_pop": sum(pop[n] for n in names)})
    for name in ["counties.geojson", "series.json", "hospitals.geojson", "event.json"]:
        print(f"{name}: {(OUT / name).stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
