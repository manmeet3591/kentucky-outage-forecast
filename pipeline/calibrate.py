"""Fit gust fragility (median, beta), restoration time constant TAU0, the crew stand-down gust
SAFE_GUST and the flood slow-down TAU_RAIN jointly on every "calibration" event in events.json,
against EAGLE-I observed outages. Test events are never seen here.

Loss per event, on statewide customers out:

    L = ln^2((sim_peak + F) / (obs_peak + F))  +  ln^2((sim_ch + 24 F) / (obs_ch + 24 F))

(peak and customer-hours, symmetric in ratio: 2x over = 2x under; floor of F customers so near-zero
events stay finite). The fit minimises the mean over events, so a 500k-customer windstorm and a 40k
thunderstorm day weigh the same. County-level skill is scored afterwards in build.py.

This loss/model form was chosen by leave-one-event-out over the calibration events only
(compare_versions.py -> version_comparison.json); the README lists every version tried.

Coordinate descent: gust fragility x TAU0 grid, then SAFE_GUST x TAU_RAIN x TAU0, repeated.
"""
import json
import math

from common import county_points, load_counties, load_events, observed
from outage_model import DEFAULT, PARAMS_FILE, lognorm_cdf, prepare, restore

MEDIANS = [90, 100, 110, 115, 120, 125, 130, 140, 150]
BETAS = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4]
TAUS = [2, 3, 4, 6, 9, 12, 18, 24, 36, 48]
SAFE_GUSTS = [55, 65, 75, 90]
TAU_RAINS = [40, 80, 160, 400]
ROUNDS = 2
F = 10000  # customers


class Event:
    """Per-county prepared weather with the (fixed, prior) rain fragility term cached."""

    def __init__(self, ev, counties):
        self.id = ev["id"]
        times, by = county_points(ev, "analysis")
        obs = observed(ev, times, counties)
        self.n = len(times)
        self.names = [n for n in counties if n in by]
        self.cust = {n: counties[n]["customers"] for n in self.names}
        self.obs = {n: [v / self.cust[n] for v in obs[n]] for n in self.names}
        self.obs_state = [sum(obs[n][t] for n in self.names) for t in range(self.n)]
        self.obs_peak, self.obs_ch = max(self.obs_state), sum(self.obs_state)
        self.preps, self.g10, self.rain_ok = {}, {}, {}
        for n in self.names:
            prep = prepare(by[n])
            self.preps[n] = prep
            self.g10[n] = [[min(3000, int(g * 10 + 0.5)) for g in pt["gust"]] for pt in prep["pts"]]
            self.rain_ok[n] = [[(1 - lognorm_cdf(pt["r24"][t], **DEFAULT["rain24"])) * (1 - lognorm_cdf(pt["r72"][t], **DEFAULT["rain72"]))
                                for t in range(self.n)] for pt in prep["pts"]]

    def damage(self, table):
        """table[g*10] = F_gust(g) -> {county: hourly county-mean damage}"""
        out = {}
        for n in self.names:
            D = [0.0] * self.n
            k = len(self.g10[n])
            for g10, rok in zip(self.g10[n], self.rain_ok[n]):
                for t in range(self.n):
                    D[t] += (1 - (1 - table[g10[t]]) * rok[t]) / k
            out[n] = D
        return out

    def loss(self, Ds, p):
        """-> (loss, simulated statewide peak, simulated customer-hours)"""
        state = [0.0] * self.n
        for n in self.names:
            c = self.cust[n]
            for t, u in enumerate(restore(self.preps[n], Ds[n], p)):
                state[t] += u * c
        peak, ch = max(state), sum(state)
        L = math.log((peak + F) / (self.obs_peak + F)) ** 2 + math.log((ch + 24 * F) / (self.obs_ch + 24 * F)) ** 2
        return L, peak, ch


def gust_table(median, beta):
    return [lognorm_cdf(i / 10, median, beta) for i in range(3001)]


def evaluate(evs, Ds, p):
    per = {e.id: e.loss(Ds[e.id], p) for e in evs}
    return sum(v[0] for v in per.values()) / len(per), per


def main():
    _, counties = load_counties()
    evs = [Event(e, counties) for e in load_events() if e["role"] == "calibration"]
    print(f"{len(evs)} calibration events: {', '.join(e.id for e in evs)}")
    p = json.loads(json.dumps(DEFAULT))
    best = None
    for rnd in range(ROUNDS):
        # 1. gust fragility x TAU0 (restoration settings fixed)
        for med in MEDIANS:
            for beta in BETAS:
                tab = gust_table(med, beta)
                Ds = {e.id: e.damage(tab) for e in evs}
                for tau in TAUS:
                    q = {**p, "gust": {"median": med, "beta": beta}, "TAU0": tau}
                    L, per = evaluate(evs, Ds, q)
                    if best is None or L < best[0]:
                        best = (L, q, per)
            print(f"round {rnd + 1} median {med}: best loss {best[0]:.4f} gust {best[1]['gust']} TAU0 {best[1]['TAU0']}")
        p = best[1]
        # 2. restoration: SAFE_GUST x TAU_RAIN x TAU0 at the best fragility
        tab = gust_table(**p["gust"])
        Ds = {e.id: e.damage(tab) for e in evs}
        for sg in SAFE_GUSTS:
            for tr in TAU_RAINS:
                for tau in TAUS:
                    q = {**p, "SAFE_GUST": sg, "TAU_RAIN": tr, "TAU0": tau}
                    L, per = evaluate(evs, Ds, q)
                    if L < best[0]:
                        best = (L, q, per)
        p = best[1]
        print(f"round {rnd + 1}: loss {best[0]:.4f} SAFE_GUST {p['SAFE_GUST']} TAU_RAIN {p['TAU_RAIN']} TAU0 {p['TAU0']}")

    L, p, per = best
    events = {}
    for e in evs:
        loss, peak, ch = per[e.id]
        events[e.id] = {"loss": round(loss, 3), "sim_peak": round(peak), "obs_peak": round(e.obs_peak),
                        "peak_ratio": round(peak / e.obs_peak, 3), "customer_hours_ratio": round(ch / e.obs_ch, 3)}
        print(f"  {e.id}: loss {loss:.2f} peak {peak:,.0f} vs obs {e.obs_peak:,.0f}")
    PARAMS_FILE.write_text(json.dumps({
        "calibrated_on": [e.id for e in evs],
        "loss": f"mean over events of ln^2 statewide peak ratio + ln^2 customer-hours ratio (floor {F} customers)",
        "mean_loss": round(L, 4), "events": events,
        "params": {k: p[k] for k in ["gust", "TAU0", "SAFE_GUST", "TAU_RAIN"]},
        "grid": {"medians": MEDIANS, "betas": BETAS, "taus": TAUS, "safe_gusts": SAFE_GUSTS, "tau_rains": TAU_RAINS},
    }, indent=1))
    print("saved", PARAMS_FILE)


if __name__ == "__main__":
    main()
