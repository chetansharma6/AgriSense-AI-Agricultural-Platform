"""Local production history, yields and prices from NASS Quick Stats.

Uses the committed historical USDA export by default, without network calls.
NASS_USE_SNAPSHOT=false selects five disk-cached Quick Stats queries instead:
state yields/prices and county harvested/bearing acreage/yields. Missing or
invalid exports also fall back to that live path. No query is made per crop.
"""

from dataclasses import dataclass
import csv
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from app import config
from app.clients import nass
from app.crops import Crop

FIRST_YEAR = "2014"
RECENT_YEARS = 5
ANNUAL_PERIODS = {"YEAR", "MARKETING YEAR"}
log = logging.getLogger(__name__)


@dataclass
class CountyAcreage:
    """Latest Census acreage for a crop in the county."""
    year: int | None  # None: never reported since 2012
    acres: float | None  # None: not reported, or withheld ("(D)")

    @property
    def grown(self) -> bool:
        return self.year is not None


@dataclass
class Market:
    county_rows: list[dict[str, Any]] | None  # area harvested; None if county unknown
    state_rows: list[dict[str, Any]]
    county_yield_rows: list[dict[str, Any]]
    source: str = "live"
    data_period: str = ""


def load_market(county_fips: str | None, *, deadline: float | None = None) -> Market:
    """Fetch (or read cached) NASS data for Florida and the county.
    Queries share the caller's absolute deadline and run in this provider
    worker, so recommendation requests cannot create nested worker pools."""
    if config.NASS_USE_SNAPSHOT:
        try:
            return _snapshot_market(county_fips)
        except (OSError, ValueError, KeyError, csv.Error):
            log.warning("Bundled NASS export unavailable or invalid; trying live NASS")
    state_rows = _state_query("YIELD", deadline) + _state_query("PRICE RECEIVED", deadline)
    if not county_fips:
        return Market(None, state_rows, [])
    county_ansi = county_fips[-3:]
    harvested = _county_query(county_ansi, "AREA HARVESTED", "2012", deadline)
    # Strawberries are reported as bearing acreage since 2017.
    bearing = _county_query(county_ansi, "AREA BEARING", "2012", deadline)
    county_yield = _county_query(county_ansi, "YIELD", FIRST_YEAR, deadline)
    return Market(harvested + bearing, state_rows, county_yield)


@lru_cache(maxsize=4)
def _snapshot_rows(path: Path) -> tuple[dict[str, Any], ...]:
    """Decode the committed exporter format into ordinary Quick Stats rows."""
    with path.open(newline="") as file:
        rows = [
            {"short_desc": row["short_desc"], "year": row["year"], "Value": row["value_raw"],
             "statisticcat_desc": row["statistic"], "domain_desc": "TOTAL",
             "agg_level_desc": row["level"].upper(), "county_fips": row["county_fips"],
             "reference_period_desc": "MARKETING YEAR" if row["statistic"] == "PRICE RECEIVED" else "YEAR"}
            for row in csv.DictReader(file)
        ]
    if not rows or not nass._valid_rows(rows):
        raise ValueError("Invalid NASS export")
    return tuple(rows)


def _snapshot_market(county_fips: str | None) -> Market:
    directory = config.DATA_DIR / "processed"
    state_rows = [*_snapshot_rows(directory / "nass_yield_state.csv"),
                  *_snapshot_rows(directory / "nass_price_state.csv")]
    acreage = _snapshot_rows(directory / "nass_acres_county.csv")
    yields = _snapshot_rows(directory / "nass_yield_county.csv")
    all_years = [int(row["year"]) for row in (*state_rows, *acreage, *yields)]
    return Market(
        [row for row in acreage if row["county_fips"] == county_fips] if county_fips else None,
        state_rows, [row for row in yields if row["county_fips"] == county_fips],
        source="snapshot", data_period=f"{min(all_years)}-{max(all_years)}; recent five reported years used for averages",
    )


def county_acreage(market: Market, crop: Crop) -> CountyAcreage | None:
    """Most recent county acreage for the crop, or None if the county is unknown."""
    if market.county_rows is None:
        return None
    reported = [
        row for row in market.county_rows
        if row["short_desc"] in crop.nass.acres_descs and row["domain_desc"] == "TOTAL" and _grown(row["Value"])
    ]
    if not reported:
        return CountyAcreage(year=None, acres=None)
    latest = max(reported, key=lambda row: int(row["year"]))
    return CountyAcreage(year=int(latest["year"]), acres=_number(latest["Value"]))


def average_yield(market: Market, crop: Crop) -> dict[str, Any] | None:
    """Mean of the most recent years: county level if reported, else state."""
    unit = _unit(crop.nass.yield_desc)
    for level, rows in (("county", market.county_yield_rows), ("state", market.state_rows)):
        values = _recent_values(rows, crop.nass.yield_desc)
        if values:
            return {"value": round(sum(values) / len(values), 1), "unit": unit, "level": level}
    return None


def price_range(market: Market, crop: Crop) -> dict[str, Any] | None:
    """Low and high Florida price received over the most recent years."""
    values = _recent_values(market.state_rows, crop.nass.price_desc)
    if not values:
        return None
    return {"low": round(min(values), 2), "high": round(max(values), 2), "unit": _unit(crop.nass.price_desc)}


def _state_query(stat: str, deadline: float | None = None) -> list[dict[str, Any]]:
    # Annual figures only: yields are reported per YEAR, prices per MARKETING YEAR.
    period = "MARKETING YEAR" if stat == "PRICE RECEIVED" else "YEAR"
    params = {
        "state_alpha": "FL", "agg_level_desc": "STATE", "statisticcat_desc": stat,
        "year__GE": FIRST_YEAR, "sector_desc": "CROPS", "reference_period_desc": period,
    }
    return nass.query(params) if deadline is None else nass.query(params, deadline=deadline)


def _county_query(county_ansi: str, stat: str, first_year: str,
                  deadline: float | None = None) -> list[dict[str, Any]]:
    params = {
        "state_alpha": "FL", "county_ansi": county_ansi, "agg_level_desc": "COUNTY",
        "statisticcat_desc": stat, "year__GE": first_year, "sector_desc": "CROPS",
    }
    if deadline is None:
        return nass.query(params, invalid_means_empty=True)
    return nass.query(params, invalid_means_empty=True, deadline=deadline)


def _recent_values(rows: list[dict[str, Any]], short_desc: str) -> list[float]:
    by_year: dict[int, float] = {}
    for row in rows:
        if row["short_desc"] != short_desc or row["reference_period_desc"] not in ANNUAL_PERIODS:
            continue
        value = _number(row["Value"])
        if value is not None:
            by_year[int(row["year"])] = value
    recent = sorted(by_year)[-RECENT_YEARS:]
    return [by_year[year] for year in recent]


def _number(raw: str) -> float | None:
    try:
        return float(raw.replace(",", "").strip())
    except ValueError:  # "(D)" withheld, "(Z)" less than half a unit, etc.
        return None


def _grown(raw: str) -> bool:
    """Withheld values '(D)' still mean the crop is grown in the county."""
    value = _number(raw)
    return value > 0 if value is not None else raw.strip() == "(D)"


def _unit(short_desc: str) -> str:
    return short_desc.split("MEASURED IN ", 1)[1]
