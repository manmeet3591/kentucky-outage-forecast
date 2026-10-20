"""Leave-one-event-out comparison of the model/loss versions tried during multi-event calibration,
on calibration events only (test events are never loaded). For each held-out event, each version's
restoration settings are refitted on the other 21 events with that version's own loss, then scored on
the held-out event with common metrics: |ln(sim/obs time to 90% restored)| and the MSE of the
peak-aligned, peak-normalised 96 h restoration curve. Gust fragility is fixed at 130 km/h, beta 0.4,
which every version's full fit selected, so statewide peaks are identical across versions.
Writes version_comparison.json. ~10 min."""
import itertools
import json
import math
import pathlib

import calibrate as C
from common import load_counties, load_events
from outage_model import DEFAULT, restore

_, counties = load_counties()
evs = [C.Event(e, counties) for e in load_events() if e["role"] == "calibration"]
tab = C.gust_table(130, 0.4)
F, H = 10000, 96
def after_peak(c):
    pk = max(c); i = c.index(pk); seg = [x / pk for x in c[i:i + H]]
    return seg + [seg[-1]] * (H - len(seg))
def etr90(c):
    pk = max(c); i = c.index(pk)
    for j in range(i, len(c)):
        if c[j] <= 0.1 * pk: return j - i
    return len(c) - i  # beyond window: cap
Ds = {e.id: e.damage(tab) for e in evs}
grid = list(itertools.product([2, 4, 6, 9, 12, 18, 24, 36, 48], [0.05, 0.1, 0.2, 0.5, 1000], [65, 90], [80, 400]))
rows = {}  # combo -> {event: dict of loss terms and held-out metrics}
for k, (tau, tl, sg, tr) in enumerate(grid):
    p = {**DEFAULT, "gust": {"median": 130, "beta": 0.4}, "TAU0": tau, "TAU_LOAD": tl, "SAFE_GUST": sg, "TAU_RAIN": tr}
    r = {}
    for e in evs:
        st = [0.0] * e.n
        for n in e.names:
            for t, u in enumerate(restore(e.preps[n], Ds[e.id][n], p)): st[t] += u * e.cust[n]
        pk, ch = max(st), sum(st)
        mag = math.log((pk + F) / (e.obs_peak + F)) ** 2
        r[e.id] = {
            "v2_logch": mag + math.log((ch + 24 * F) / (e.obs_ch + 24 * F)) ** 2,
            "v3_shape": mag + sum((s / pk - o / e.obs_peak) ** 2 for s, o in zip(st, e.obs_state)) / e.n,
            "v5_decay": mag + sum((a - b) ** 2 for a, b in zip(after_peak(st), after_peak(e.obs_state))) / H,
            "etr_err": abs(math.log(etr90(st) / etr90(e.obs_state))),
            "decay_mse": sum((a - b) ** 2 for a, b in zip(after_peak(st), after_peak(e.obs_state))) / H,
        }
    rows[(tau, tl, sg, tr)] = r
    if k % 20 == 0: print(f"{k}/{len(grid)} settings")
versions = {  # name: (loss key, allowed combos)
    "v2 log peak + log customer-hours, no crew saturation": ("v2_logch", lambda c: c[1] == 1000),
    "v3 log peak + unaligned curve shape, no crew saturation": ("v3_shape", lambda c: c[1] == 1000),
    "v4 log peak + unaligned curve shape, crew saturation (TAU_LOAD)": ("v3_shape", lambda c: True),
    "v5a log peak + aligned post-peak decay, no crew saturation": ("v5_decay", lambda c: c[1] == 1000),
    "v5 log peak + aligned post-peak decay, crew saturation (TAU_LOAD)": ("v5_decay", lambda c: True),
}
out = {}
for name, (key, ok) in versions.items():
    combos = [c for c in grid if ok(c)]
    etr, dec, picks = [], [], []
    for held in evs:
        train = [e.id for e in evs if e.id != held.id]
        best = min(combos, key=lambda c: sum(rows[c][i][key] for i in train))
        picks.append(best)
        etr.append(rows[best][held.id]["etr_err"]); dec.append(rows[best][held.id]["decay_mse"])
    full = min(combos, key=lambda c: sum(rows[c][e.id][key] for e in evs))
    out[name] = {"loeo_mean_abs_log_etr90_ratio": round(sum(etr) / len(etr), 3),
                 "loeo_median_etr90_factor": round(math.exp(sorted(etr)[len(etr) // 2]), 2),
                 "loeo_mean_decay_mse": round(sum(dec) / len(dec), 4),
                 "full_fit": dict(zip(["TAU0", "TAU_LOAD", "SAFE_GUST", "TAU_RAIN"], full)),
                 "distinct_fold_picks": len(set(picks))}
    print(name, out[name])
pathlib.Path(__file__).with_name("version_comparison.json").write_text(json.dumps(out, indent=1))
