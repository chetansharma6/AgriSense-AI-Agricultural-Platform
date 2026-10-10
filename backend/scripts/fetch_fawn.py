"""Download the FAWN station list and every station's daily minimums into the cache.

Run once (and again to refresh); the results are committed so the app never
waits on FAWN. From backend/:
    python -m scripts.fetch_fawn
"""

import json
import time

import httpx

from app.clients import fawn
from app.clients.fawn import STATIONS_FILE, FawnError, daily_min_c

STATIONS_URL = "https://fawn.ifas.ufl.edu/controller.php/latestobsjson/"


def main() -> None:
    feed = httpx.get(STATIONS_URL, timeout=60).raise_for_status().json()["stnsWxData"]
    stations = []
    for item in sorted(feed, key=lambda s: int(s["stnID"])):
        try:
            years = len(daily_min_c(item["stnID"])) / 365.25
        except FawnError:
            years = 0.0
        stations.append({"id": item["stnID"], "name": item["stnName"], "lat": item["lat"],
                         "lon": item["lng"], "years": round(years, 1)})
        print(f"{item['stnID']:>4} {item['stnName']:<28} {years:4.1f} years")
        time.sleep(0.3)  # be polite to FAWN
    STATIONS_FILE.write_text(json.dumps(stations, indent=1) + "\n")
    fawn.load_stations.cache_clear()
    print(f"\n{len(fawn.load_stations())} of {len(stations)} stations have >= {fawn.MIN_YEARS:g} years; "
          f"wrote {STATIONS_FILE.name}")


if __name__ == "__main__":
    main()
