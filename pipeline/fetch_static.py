"""Kentucky counties (Census TIGERweb), electricity customers (EAGLE-I MCC) and critical assets (OSM)."""
import csv
import io
import json
import pathlib
import time

import requests

RAW = pathlib.Path(__file__).resolve().parent.parent / "raw"
UA = {"User-Agent": "kentucky-outage-forecast/0.1 (research; github.com/manmeet3591)"}
MCC_URL = "https://ndownloader.figshare.com/files/42547708"  # EAGLE-I modeled customer counts per county
TIGER = ("https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query"
         "?where=STATE%3D%2721%27&outFields=NAME,GEOID&f=geojson&geometryPrecision=4"
         "&maxAllowableOffset=0.004&returnGeometry=true")
OVERPASS = "https://overpass-api.de/api/interpreter"
ASSETS = {
    "hospital": 'nwr["amenity"="hospital"](area.k);',
    "substation": 'nwr["power"="substation"](area.k);',
    "power_plant": 'nwr["power"="plant"](area.k);',
}


def counties():
    g = requests.get(TIGER, timeout=120, headers=UA).json()
    text = requests.get(MCC_URL, timeout=120, headers=UA).content.decode("utf-8-sig")
    cust = {r["County_FIPS"].zfill(5): int(r["Customers"]) for r in csv.DictReader(io.StringIO(text))}
    for f in g["features"]:
        fips = f["properties"]["GEOID"]
        f["properties"] = {"name": f["properties"]["NAME"].replace(" County", ""), "fips": fips,
                           "customers": cust.get(fips)}
    missing = [f["properties"]["name"] for f in g["features"] if not f["properties"]["customers"]]
    print(f"counties: {len(g['features'])}, customers: {sum(f['properties']['customers'] or 0 for f in g['features']):,}, missing: {missing}")
    (RAW / "counties.geojson").write_text(json.dumps(g))


def assets():
    feats = []
    for cat, sel in ASSETS.items():
        q = f'[out:json][timeout:180];area["ISO3166-2"="US-KY"]->.k;({sel});out center tags;'
        for i in range(4):
            r = requests.post(OVERPASS, data={"data": q}, headers=UA, timeout=300)
            if r.status_code == 200:
                break
            time.sleep(30 * (i + 1))
        els = r.json()["elements"]
        for e in els:
            lon, lat = (e["lon"], e["lat"]) if "lon" in e else (e["center"]["lon"], e["center"]["lat"])
            t = e.get("tags", {})
            feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
                          "properties": {"cat": cat, "name": t.get("name"), "operator": t.get("operator")}})
        print(f"{cat}: {len(els)}")
        time.sleep(5)
    (RAW / "assets.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))


if __name__ == "__main__":
    RAW.mkdir(exist_ok=True)
    counties()
    assets()
