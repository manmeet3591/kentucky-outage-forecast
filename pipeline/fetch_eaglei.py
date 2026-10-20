"""Stream EAGLE-I yearly county outage files (figshare, ~1.2 GB each) and keep Kentucky rows only.

Source: Brelsford et al., "The Environment for Analysis of Geo-Located Energy Information's
Recorded Electricity Outages 2014-2025", figshare (ORNL). 15-minute customers-out by county, UTC.
"""
import pathlib
import sys

import requests

RAW = pathlib.Path(__file__).resolve().parent.parent / "raw"
FILES = {2023: 44574907, 2024: 53581661, 2025: 62164877}


def main(years):
    for y in years:
        out = RAW / f"eaglei_ky_{y}.csv"
        n = 0
        with requests.get(f"https://ndownloader.figshare.com/files/{FILES[y]}", stream=True, timeout=600) as r, out.open("w") as f:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if line and line.startswith("21") and line[2:5].isdigit() and line[5] == ",":
                    f.write(line + "\n")
                    n += 1
        print(f"{y}: {n:,} Kentucky rows")


if __name__ == "__main__":
    main([int(y) for y in sys.argv[1:]] or [2023, 2024])
