"""Run the calibrated outage model for every event and source, compare with EAGLE-I -> docs/data/."""
import datetime as dt
import json
import math

from common import ROOT, STEP, county_points, down, load_counties, load_events, observed
from outage_model import PARAMS_FILE, load_params, simulate, summarize

OUT = ROOT / "docs" / "data"
FLAG = 0.05  # county "significant outage" when >= 5% of customers out


def pearson(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else None


def etr90(curve, step_h):
    pk = max(curve)
    i = curve.index(pk)
    for j in range(i, len(curve)):
        if curve[j] <= 0.1 * pk:
            return (j - i) * step_h
    return None


def score(sim, obs, cust, names, times3):
    """sim/obs: {county: 3-hourly fraction}. Skill of a model run against EAGLE-I."""
    st_sim = [sum(sim[n][k] * cust[n] for n in names) for k in range(len(times3))]
    st_obs = [sum(obs[n][k] * cust[n] for n in names) for k in range(len(times3))]
    ps, po = max(st_sim), max(st_obs)
    peaks_s, peaks_o = [max(sim[n]) for n in names], [max(obs[n]) for n in names]
    fo = {n for n, v in zip(names, peaks_o) if v >= FLAG}
    fs = {n for n, v in zip(names, peaks_s) if v >= FLAG}
    hours = lambda i: i * STEP
    return {
        "peak_customers": round(ps), "obs_peak_customers": round(po),
        "peak_ratio": round(ps / po, 3) if po else None,
        "peak_timing_error_h": hours(st_sim.index(ps)) - hours(st_obs.index(po)),
        "customer_hours_ratio": round(sum(st_sim) / sum(st_obs), 3) if sum(st_obs) else None,
        "corr_county_peak": round(pearson(peaks_s, peaks_o) or 0, 3),
        "corr_statewide_curve": round(pearson(st_sim, st_obs) or 0, 3),
        "hit_rate": round(len(fo & fs) / len(fo), 3) if fo else None,
        "false_alarm_ratio": round(len(fs - fo) / len(fs), 3) if fs else None,
        "n_flagged_obs": len(fo), "n_flagged_sim": len(fs),
        "etr90_h": etr90(st_sim, STEP), "obs_etr90_h": etr90(st_obs, STEP),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_params()
    calib = json.loads(PARAMS_FILE.read_text())
    gj, counties = load_counties()
    names = sorted(counties)
    cust = {n: counties[n]["customers"] for n in names}
    assets = json.loads((ROOT / "raw" / "assets.geojson").read_text())["features"]
    from geo import CountyIndex
    cidx = CountyIndex(gj["features"])
    hosp = {n: 0 for n in names}
    subs = {n: 0 for n in names}
    hosp_feats = []
    for a in assets:
        lon, lat = a["geometry"]["coordinates"]
        c = cidx.find(lon, lat)
        if not c:
            continue
        n = c["properties"]["name"]
        if a["properties"]["cat"] == "hospital":
            hosp[n] += 1
            hosp_feats.append({"type": "Feature", "geometry": a["geometry"], "properties": {"name": a["properties"]["name"], "county": n}})
        elif a["properties"]["cat"] == "substation":
            subs[n] += 1

    index = []
    for ev in load_events():
        srcs = ["analysis"] + (["lead1", "lead2", "lead3"] if ev["forecasts"] else [])
        times, _ = county_points(ev, "analysis")
        obs_h = observed(ev, times, counties)
        obs = {n: [round(v / cust[n], 4) for v in down(obs_h[n])] for n in names}
        t3 = times[::STEP]
        local = [(dt.datetime.fromisoformat(t) + dt.timedelta(hours=ev["utc_offset"])).isoformat()[:16] for t in t3]
        series = {"observed": {n: {"out": obs[n]} for n in names}}
        summary, skill = {}, {}
        for src in srcs:
            _, by = county_points(ev, src)
            series[src], summary[src] = {}, {}
            for n in names:
                U = simulate(by[n], p)
                s = summarize(U, times)
                s["customers_peak"] = round(s["peak"] * cust[n])
                s["customer_hours"] = round(s["outage_hours"] * cust[n])
                summary[src][n] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}
                series[src][n] = {
                    "out": [round(x, 4) for x in down(U)],
                    "rain": [round(x, 1) for x in down([sum((pt["rain"][t] or 0) for pt in by[n]) / len(by[n]) for t in range(len(times))], "sum")],
                    "gust": [round(x) for x in down([max((pt["gust"][t] or 0) for pt in by[n]) for t in range(len(times))], "max")],
                }
            skill[src] = score({n: series[src][n]["out"] for n in names}, obs, cust, names, t3)
            print(ev["id"], src, skill[src])
        statewide = {s: [round(sum(series[s][n]["out"][k] * cust[n] for n in names)) for k in range(len(t3))] for s in ["observed"] + srcs}
        (OUT / f"{ev['id']}.json").write_text(json.dumps({
            **ev, "times": local, "step_h": STEP, "sources": srcs, "series": series, "summary": summary,
            "skill": skill, "statewide": statewide, "flag": FLAG,
        }, separators=(",", ":")))
        index.append({k: ev[k] for k in ["id", "name", "role", "start", "end", "tz", "forecasts"]})

    for f in gj["features"]:
        n = f["properties"]["name"]
        f["properties"].update({"hospitals": hosp[n], "substations": subs[n]})
    (OUT / "counties.geojson").write_text(json.dumps(gj, separators=(",", ":")))
    (OUT / "hospitals.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": hosp_feats}, separators=(",", ":")))
    (OUT / "meta.json").write_text(json.dumps({"events": index, "params": p, "calibration": {k: calib[k] for k in ["calibrated_on", "rmse_customers", "sim_statewide_peak", "loss"]},
                                               "total_customers": sum(cust.values()), "flag": FLAG}, indent=1))
    for f in sorted(OUT.iterdir()):
        print(f"{f.name}: {f.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
