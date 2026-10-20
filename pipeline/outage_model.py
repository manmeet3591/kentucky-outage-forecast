"""Weather-driven distribution outage and restoration model.

Per sample point and hour, lognormal fragility curves give the share of customers whose supply
is interrupted by the current weather:

    D = 1 - (1 - F_gust) (1 - F_rain24) (1 - F_rain72)

  F_gust   tree-fall / conductor faults on overhead lines vs 10 m wind gust (dominant in Kentucky)
  F_rain24 flash flooding, flashovers, poles in saturated ground vs 24 h rainfall
  F_rain72 prolonged flooding / access loss vs 72 h rainfall

County outage share U then evolves hourly:

    D6        = mean county D over the last SUSTAIN_H hours
    tau       = TAU0 * (1 + R72 / TAU_RAIN)      flooding slows access and repair
    restored  = U * (1 - exp(-1 / tau)),  0 while max gust > SAFE_GUST or mean rain > SAFE_RAIN
    U         = max(D6, U - restored)

Gust fragility and TAU0 are calibrated against EAGLE-I observed outages (calibrate.py).
"""
import json
import math
import pathlib

DEFAULT = {
    "gust": {"median": 90.0, "beta": 0.25},
    "rain24": {"median": 200.0, "beta": 0.50},
    "rain72": {"median": 350.0, "beta": 0.50},
    "SUSTAIN_H": 3,
    "TAU0": 24.0,
    "TAU_RAIN": 80.0,
    "SAFE_GUST": 65.0,
    "SAFE_RAIN": 8.0,
}
PARAMS_FILE = pathlib.Path(__file__).with_name("params.json")


def load_params():
    p = json.loads(json.dumps(DEFAULT))
    if PARAMS_FILE.exists():
        p.update(json.loads(PARAMS_FILE.read_text())["params"])
    return p


def lognorm_cdf(x, median, beta):
    if x <= 0:
        return 0.0
    return 0.5 * (1 + math.erf(math.log(x / median) / (beta * math.sqrt(2))))


def rolling_sum(xs, n):
    out, s = [], 0.0
    for i, x in enumerate(xs):
        s += x
        if i >= n:
            s -= xs[i - n]
        out.append(s)
    return out


def prepare(points):
    """Clean point series once: gust, 24/72 h rain, county max gust and mean rain per hour."""
    pts = []
    for pt in points:
        rain = [x or 0.0 for x in pt["rain"]]
        pts.append({"gust": [x or 0.0 for x in pt["gust"]], "r24": rolling_sum(rain, 24), "r72": rolling_sum(rain, 72), "rain": rain})
    n = len(pts[0]["gust"])
    return {
        "pts": pts, "n": n,
        "gmax": [max(p["gust"][t] for p in pts) for t in range(n)],
        "rmean": [sum(p["rain"][t] for p in pts) / len(pts) for t in range(n)],
        "R72": [sum(p["r72"][t] for p in pts) / len(pts) for t in range(n)],
    }


def damage(prep, p):
    """County-mean hourly damage fraction D."""
    n, pts = prep["n"], prep["pts"]
    D = [0.0] * n
    for pt in pts:
        for t in range(n):
            fg = lognorm_cdf(pt["gust"][t], **p["gust"])
            f24 = lognorm_cdf(pt["r24"][t], **p["rain24"])
            f72 = lognorm_cdf(pt["r72"][t], **p["rain72"])
            D[t] += (1 - (1 - fg) * (1 - f24) * (1 - f72)) / len(pts)
    return D


def restore(prep, D, p):
    S = int(p["SUSTAIN_H"])
    U, out = 0.0, []
    for t in range(prep["n"]):
        d = sum(D[max(0, t - S + 1):t + 1]) / min(S, t + 1)
        tau = p["TAU0"] * (1 + prep["R72"][t] / p["TAU_RAIN"])
        safe = prep["gmax"][t] <= p["SAFE_GUST"] and prep["rmean"][t] <= p["SAFE_RAIN"]
        restored = U * (1 - math.exp(-1 / tau)) if safe else 0.0
        U = min(1.0, max(d, U - restored))
        out.append(U)
    return out


def simulate(points, p):
    prep = prepare(points)
    return restore(prep, damage(prep, p), p)


def summarize(U, times, step_h=1):
    peak = max(U)
    ip = U.index(peak)
    etr = None
    if peak > 0.005:
        for j in range(ip, len(U)):
            if U[j] <= 0.1 * peak:
                etr = (j - ip) * step_h
                break
    return {"peak": peak, "peak_time": times[ip], "outage_hours": sum(U) * step_h, "etr90_h": etr}
