"""Rank Kentucky outage events in EAGLE-I: statewide customers out (hourly mean of 15-min
snapshots, then a 3-hour running median so one-snapshot reporting glitches don't count),
peaks at least SEP_DAYS apart, largest first. Usage: python3 find_events.py [years...]"""
import csv
import datetime as dt
import sys

from common import RAW

SEP_DAYS = 5
TOP = 40


def statewide(y):
    tot, snaps = {}, {}
    with open(RAW / f"eaglei_ky_{y}.csv") as f:
        for row in csv.reader(f):
            h = row[4][:13]
            tot[h] = tot.get(h, 0) + float(row[3] or 0)
            snaps.setdefault(h, set()).add(row[4])
    hours = sorted(tot)
    mean = [tot[h] / len(snaps[h]) for h in hours]
    return {h + ":00": sorted(mean[max(0, i - 1):i + 2])[len(mean[max(0, i - 1):i + 2]) // 2] for i, h in enumerate(hours)}


def main(years):
    snaps = {}
    for y in years:
        snaps.update(statewide(y))
    peaks = []
    for ts, v in sorted(snaps.items(), key=lambda kv: -kv[1]):
        t = dt.datetime.fromisoformat(ts)
        if all(abs((t - p).total_seconds()) > SEP_DAYS * 86400 for p, _ in peaks):
            peaks.append((t, v))
        if len(peaks) >= TOP:
            break
    for t, v in peaks:
        print(f"{t:%Y-%m-%d %H:%M} UTC  {v:>9,.0f}")


if __name__ == "__main__":
    main(sys.argv[1:] or [2023, 2024])
