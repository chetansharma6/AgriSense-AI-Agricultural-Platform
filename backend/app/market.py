"""Local production history, yields and prices from NASS Quick Stats.

Uses five kinds of query, each cached on disk: state yields and state prices
(shared by every location), and county area harvested, county area bearing and
county yields (one of each per county). No query is made per crop.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from app.clients import nass
from app.crops import Crop

FIRST_YEAR = "2014"
RECENT_YEARS = 5
ANNUAL_PERIODS = {"YEAR", "MARKETING YEAR"}


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


def load_market(county_fips: str | None) -> Market:
    """Fetch (or read cached) NASS data for Florida and the county.
    All queries run in parallel, so a new county costs one round trip."""
    with ThreadPoolExecutor(max_workers=5) as pool:
        state_yield = pool.submit(_state_query, "YIELD")
        state_price = pool.submit(_state_query, "PRICE RECEIVED")
        county_jobs = None
        if county_fips:
            county_ansi = county_fips[-3:]
            county_jobs = (
                pool.submit(_county_query, county_ansi, "AREA HARVESTED", "2012"),
                # Strawberries are reported as bearing acreage since 2017.
                pool.submit(_county_query, county_ansi, "AREA BEARING", "2012"),
                pool.submit(_county_query, county_ansi, "YIELD", FIRST_YEAR),
            )
        state_rows = state_yield.result() + state_price.result()
        if county_jobs is None:
            return Market(None, state_rows, [])
        harvested, bearing, county_yield = (job.result() for job in county_jobs)
    return Market(harvested + bearing, state_rows, county_yield)


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


def _state_query(stat: str) -> list[dict[str, Any]]:
    # Annual figures only: yields are reported per YEAR, prices per MARKETING YEAR.
    period = "MARKETING YEAR" if stat == "PRICE RECEIVED" else "YEAR"
    return nass.query({
        "state_alpha": "FL", "agg_level_desc": "STATE", "statisticcat_desc": stat,
        "year__GE": FIRST_YEAR, "sector_desc": "CROPS", "reference_period_desc": period,
    })


def _county_query(county_ansi: str, stat: str, first_year: str) -> list[dict[str, Any]]:
    params = {
        "state_alpha": "FL", "county_ansi": county_ansi, "agg_level_desc": "COUNTY",
        "statisticcat_desc": stat, "year__GE": first_year, "sector_desc": "CROPS",
    }
    return nass.query(params, invalid_means_empty=True)


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
