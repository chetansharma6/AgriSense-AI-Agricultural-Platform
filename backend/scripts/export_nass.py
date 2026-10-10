"""Export the USDA NASS Quick Stats data behind AgriSense to CSV for inspection.

Writes data/processed/nass_*.csv with the same series and filters the app uses
(annual figures, TOTAL domain), for every Florida county. Needs NASS_API_KEY.
About 200 requests, one at a time with backoff (NASS's gateway blocks bursts),
so it takes several minutes. Responses are cached in the system temp folder,
not data/cache, so a rerun resumes where it stopped. From backend/:
    python -m scripts.export_nass
"""

import csv
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from app import cache
from app.clients.nass import NassError
from app.config import DATA_DIR
from app.crops import Crop, load_crops
from app.market import ANNUAL_PERIODS, FIRST_YEAR, _county_query, _number, _state_query, _unit

# Florida county FIPS codes: odd 001-133, except Miami-Dade, which is 086 (not 025).
FL_COUNTIES = sorted({f"{n:03d}" for n in range(1, 134, 2)} - {"025"} | {"086"})
COLUMNS = ["crop_id", "level", "county_fips", "county_name", "year", "statistic", "short_desc", "unit",
           "value", "value_raw"]
OUT_DIR = DATA_DIR / "processed"
REQUEST_GAP_S = 1.0  # NASS's gateway answers 403 to bursts
RETRY_WAITS_S = (15, 30, 60, 120)
EXPORT_CACHE = Path(tempfile.gettempdir()) / "agrisense-nass-export"


def series_by_desc(crops: Iterable[Crop]) -> dict[str, tuple[str, str]]:
    """NASS short_desc -> (crop id, kind) for every series the app reads."""
    series: dict[str, tuple[str, str]] = {}
    for crop in crops:
        series[crop.nass.yield_desc] = (crop.id, "yield")
        series[crop.nass.price_desc] = (crop.id, "price")
        for desc in crop.nass.acres_descs:
            series[desc] = (crop.id, "acres")
    return series


def records(rows: list[dict[str, Any]], series: dict[str, tuple[str, str]], kind: str, level: str,
            county_ansi: str | None = None) -> list[dict[str, Any]]:
    """Rows the app would use for this kind of series, as CSV records."""
    out = []
    for row in rows:
        crop_id, row_kind = series.get(row.get("short_desc", ""), (None, None))
        if row_kind != kind:
            continue
        if kind == "acres" and row.get("domain_desc") != "TOTAL":
            continue
        if kind != "acres" and row.get("reference_period_desc") not in ANNUAL_PERIODS:
            continue
        value = _number(row["Value"])
        ansi = county_ansi or row.get("county_ansi") or ""
        out.append({
            "crop_id": crop_id, "level": level,
            "county_fips": f"12{ansi}" if ansi else "", "county_name": (row.get("county_name") or "").title(),
            "year": int(row["year"]), "statistic": row.get("statisticcat_desc", ""),
            "short_desc": row["short_desc"],
            # Acreage series ("PEANUTS - ACRES HARVESTED") carry no "MEASURED IN" part.
            "unit": "ACRES" if kind == "acres" else _unit(row["short_desc"]),
            "value": "" if value is None else value, "value_raw": row["Value"].strip(),
        })
    return sorted(out, key=lambda r: (r["crop_id"], r["county_fips"], r["year"], r["short_desc"]))


def polite(fetch: Any, *args: Any) -> list[dict[str, Any]]:
    """One NASS query, retried with growing waits when the gateway pushes back."""
    for wait in (*RETRY_WAITS_S, None):
        try:
            rows = fetch(*args)
            time.sleep(REQUEST_GAP_S)
            return rows
        except NassError as error:
            if wait is None or not any(f"({code})" in str(error) for code in (403, 429, 500, 502, 503, 504)):
                raise
            print(f"\n  NASS pushed back ({str(error)[:40]}...); waiting {wait} s", flush=True)
            time.sleep(wait)
    raise AssertionError("unreachable")


def _county(ansi: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [polite(_county_query, ansi, stat, first_year)
            for stat, first_year in (("AREA HARVESTED", "2012"), ("AREA BEARING", "2012"), ("YIELD", FIRST_YEAR))]
    return rows[0] + rows[1], rows[2]


def write(name: str, rows: list[dict[str, Any]]) -> None:
    with (OUT_DIR / name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    series = series_by_desc(load_crops().values())
    cache.CACHE_DIR = EXPORT_CACHE  # keep ~200 county responses out of data/cache
    state_yield = records(polite(_state_query, "YIELD"), series, "yield", "state")
    state_price = records(polite(_state_query, "PRICE RECEIVED"), series, "price", "state")
    county_acres: list[dict[str, Any]] = []
    county_yield: list[dict[str, Any]] = []
    failed = []
    for done, ansi in enumerate(FL_COUNTIES, start=1):
        try:
            acres_rows, yield_rows = _county(ansi)
        except NassError as error:
            failed.append(ansi)
            print(f"\n  county 12{ansi} skipped: {str(error)[:80]}", flush=True)
            continue
        county_acres += records(acres_rows, series, "acres", "county", ansi)
        county_yield += records(yield_rows, series, "yield", "county", ansi)
        print(f"\rcounties: {done}/{len(FL_COUNTIES)}", end="", flush=True)
    print()
    if failed:
        raise SystemExit(f"{len(failed)} counties failed ({', '.join(failed)}); nothing written. Rerun to resume.")
    files = {"nass_yield_state.csv": state_yield, "nass_price_state.csv": state_price,
             "nass_acres_county.csv": county_acres, "nass_yield_county.csv": county_yield}
    OUT_DIR.mkdir(exist_ok=True)
    for name, rows in files.items():
        write(name, sorted(rows, key=lambda r: (r["crop_id"], r["county_fips"], r["year"], r["short_desc"])))

    crop_ids = list(load_crops())
    print(f"\n{'crop':<12}" + "".join(f"{name.removeprefix('nass_').removesuffix('.csv'):>14}" for name in files))
    counts = {name: Counter(r["crop_id"] for r in rows) for name, rows in files.items()}
    for crop_id in crop_ids:
        print(f"{crop_id:<12}" + "".join(f"{counts[name][crop_id]:>14}" for name in files))
    print(f"\nwrote {', '.join(files)} to {OUT_DIR.relative_to(DATA_DIR.parent)}")


if __name__ == "__main__":
    main()
