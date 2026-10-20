"""Fit gust fragility (median, beta) and restoration time constant TAU0 on the calibration event,
against EAGLE-I observed county outages. Loss = RMSE of customers out per county per hour.
Test events are never seen here."""
import json
import math

from common import county_points, load_counties, load_events, observed
from outage_model import DEFAULT, PARAMS_FILE, damage, prepare, restore

MEDIANS = [60, 65, 70, 75, 80, 85, 90, 95, 100, 110, 120]
BETAS = [0.15, 0.2, 0.25, 0.3, 0.35, 0.45]
TAUS = [6, 12, 18, 24, 36, 48, 72]


def main():
    ev = next(e for e in load_events() if e["role"] == "calibration")
    _, counties = load_counties()
    times, by = county_points(ev, "analysis")
    obs = observed(ev, times, counties)
    preps = {n: prepare(by[n]) for n in counties}
    cust = {n: counties[n]["customers"] for n in counties}
    obs_frac = {n: [v / cust[n] for v in obs[n]] for n in counties}
    print("observed statewide peak:", round(max(sum(obs[n][t] for n in counties) for t in range(len(times)))))

    best = None
    results = []
    for med in MEDIANS:
        for beta in BETAS:
            p = json.loads(json.dumps(DEFAULT))
            p["gust"] = {"median": med, "beta": beta}
            Ds = {n: damage(preps[n], p) for n in counties}
            for tau in TAUS:
                p["TAU0"] = tau
                se, cnt, state_sim = 0.0, 0, [0.0] * len(times)
                for n in counties:
                    U = restore(preps[n], Ds[n], p)
                    for t, (u, o) in enumerate(zip(U, obs_frac[n])):
                        se += ((u - o) * cust[n]) ** 2
                        state_sim[t] += u * cust[n]
                    cnt += len(U)
                rmse = math.sqrt(se / cnt)
                peak = max(state_sim)
                results.append((rmse, med, beta, tau, peak))
                if best is None or rmse < best[0]:
                    best = (rmse, med, beta, tau, peak)
        print(f"median {med}: best so far rmse={best[0]:.0f} median={best[1]} beta={best[2]} tau={best[3]} peak={best[4]:.0f}")

    rmse, med, beta, tau, peak = best
    PARAMS_FILE.write_text(json.dumps({
        "calibrated_on": ev["id"], "loss": "RMSE customers out per county-hour",
        "rmse_customers": round(rmse, 1), "sim_statewide_peak": round(peak),
        "params": {"gust": {"median": med, "beta": beta}, "TAU0": tau},
        "grid": {"medians": MEDIANS, "betas": BETAS, "taus": TAUS},
    }, indent=1))
    print("saved", PARAMS_FILE.read_text())


if __name__ == "__main__":
    main()
