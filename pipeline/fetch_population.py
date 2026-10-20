"""County populations (KNBS 2019 census) from the Wikipedia 'Counties of Kenya' table."""
import json
import pathlib
import re

import requests

RAW = pathlib.Path(__file__).resolve().parent.parent / "raw"
# Wikipedia name -> geoBoundaries name
ALIASES = {"Taita–Taveta": "Taita Taveta", "Tharaka-Nithi": "Tharaka", "Tharaka Nithi": "Tharaka",
           "Elgeyo Marakwet": "Elgeyo-Marakwet", "Muranga": "Murang'a", "Homa bay": "Homa Bay", "Trans-Nzoia": "Trans Nzoia"}


def main():
    r = requests.get("https://en.wikipedia.org/w/api.php", timeout=60,
                     headers={"User-Agent": "kenya-outage-forecast/0.1 (research)"},
                     params={"action": "parse", "page": "Counties_of_Kenya", "prop": "wikitext",
                             "format": "json", "section": 2})
    text = r.json()["parse"]["wikitext"]["*"]
    pop = {}
    for row in text.split("|-"):
        m = re.search(r"\|\s*\d{1,3}\s*\|\|.*?\[\[([^\]|]+?)(?:\|([^\]]+))?\]\]", row)
        if not m:
            continue
        name = (m.group(2) or m.group(1)).replace(" County", "").strip()
        nums = re.findall(r"align=\"right\"\s*\|\s*([\d,\.]+)", row)
        if len(nums) >= 3:  # area, pop 2009, pop 2019
            pop[ALIASES.get(name, name)] = int(nums[2].replace(",", ""))
    RAW.mkdir(exist_ok=True)
    (RAW / "population.json").write_text(json.dumps(pop, indent=1))
    print(f"{len(pop)} counties, total {sum(pop.values()):,}")


if __name__ == "__main__":
    main()
