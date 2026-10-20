"""Weather-driven distribution outage and restoration model (prototype, physics/fragility based).

For each sample point and hour, the fraction of customers whose supply is interrupted by the
current weather is given by lognormal fragility curves:

    D = 1 - (1 - F_gust) (1 - F_rain24) (1 - F_rain72)

  F_gust   tree-fall / conductor-clash faults on overhead lines vs 10 m wind gust
  F_rain24 water ingress, flashovers, pole failures in saturated ground vs 24 h rainfall
  F_rain72 flooding of substations / landslides / access loss vs 72 h rainfall

The county outage state U (fraction of people without power) then evolves hourly:

    D6        = mean of D over the last SUSTAIN_H hours            # faults need sustained exposure
    restored  = U * (1 - exp(-1 / tau))                           # crews restore with time constant tau
    tau       = TAU0 * (1 + R72 / TAU_RAIN)                       # flooding slows access and repair
    restored  = 0 while max gust > SAFE_GUST or county-mean rain > SAFE_RAIN (crew stand-down)
    U         = max(D6, U - restored)                             # current damage, or backlog not yet restored

Parameters are priors chosen for ERA5/GFS-scale (smoothed) intensities. They are meant to be
recalibrated (or replaced by a learned model) against utility outage logs, e.g. KPLC
interruption records, see README.
"""
import math

PARAMS = {
    "gust": {"median": 75.0, "beta": 0.30},     # km/h (50 -> ~9%, 60 -> ~23%)
    "rain24": {"median": 250.0, "beta": 0.50},  # mm  (100 mm -> ~3%, 150 mm -> ~15%)
    "rain72": {"median": 400.0, "beta": 0.50},  # mm  (200 mm -> ~8%)
    "SUSTAIN_H": 6.0,
    "TAU0": 10.0,       # h, typical fault restoration time constant in dry, calm weather
    "TAU_RAIN": 80.0,   # mm of 72 h rain that doubles restoration time
    "SAFE_GUST": 60.0,  # km/h
    "SAFE_RAIN": 5.0,   # mm/h, county mean
}


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


def point_damage(rain, gust, p=PARAMS):
    """Hourly damage fraction D and 72 h rain for one point."""
    rain = [x or 0.0 for x in rain]
    gust = [x or 0.0 for x in gust]
    r24, r72 = rolling_sum(rain, 24), rolling_sum(rain, 72)
    d = []
    for g, a, b in zip(gust, r24, r72):
        fg = lognorm_cdf(g, **p["gust"])
        f24 = lognorm_cdf(a, **p["rain24"])
        f72 = lognorm_cdf(b, **p["rain72"])
        d.append(1 - (1 - fg) * (1 - f24) * (1 - f72))
    return d, r72


def simulate(points, p=PARAMS):
    """points: list of dicts with hourly 'rain' and 'gust'. Returns county-level hourly series."""
    n = len(points[0]["rain"])
    dmg = [point_damage(pt["rain"], pt["gust"], p) for pt in points]
    D = [sum(d[0][t] for d in dmg) / len(dmg) for t in range(n)]
    R72 = [sum(d[1][t] for d in dmg) / len(dmg) for t in range(n)]
    gmax = [max((pt["gust"][t] or 0) for pt in points) for t in range(n)]
    rmean = [sum((pt["rain"][t] or 0) for pt in points) / len(points) for t in range(n)]
    S = int(p["SUSTAIN_H"])
    U, out, new_s, rest_s = 0.0, [], [], []
    for t in range(n):
        d6 = sum(D[max(0, t - S + 1):t + 1]) / min(S, t + 1)
        tau = p["TAU0"] * (1 + R72[t] / p["TAU_RAIN"])
        safe = gmax[t] <= p["SAFE_GUST"] and rmean[t] <= p["SAFE_RAIN"]
        restored = U * (1 - math.exp(-1 / tau)) if safe else 0.0
        nxt = max(d6, U - restored)
        new_s.append(max(0.0, nxt - (U - restored)))
        rest_s.append(restored)
        U = min(1.0, nxt)
        out.append(U)
    return {"U": out, "D": D, "R72": R72, "new": new_s, "restored": rest_s}


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
