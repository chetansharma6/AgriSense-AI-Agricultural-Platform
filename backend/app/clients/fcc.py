"""FCC Census Area API: lat/lon -> county name and FIPS code."""

from typing import TypedDict

from app.cache import read_cache, write_cache
from app.clients.http import http

FCC_URL = "https://geo.fcc.gov/api/census/area"


class County(TypedDict):
    county: str
    county_fips: str
    state: str


def lookup_county(lat: float, lon: float) -> County | None:
    """Return the county for a point, or None if the point is not in a county."""
    params = {"lat": round(lat, 4), "lon": round(lon, 4)}
    cached = read_cache("fcc", params)
    if cached is not None:
        return cached or None

    response = http().get(FCC_URL, params={**params, "format": "json"})
    response.raise_for_status()
    results = response.json().get("results", [])
    county: County | dict = {}
    if results:
        first = results[0]
        county = {
            "county": first["county_name"].removesuffix(" County"),
            "county_fips": first["county_fips"],
            "state": first["state_code"],
        }
    write_cache("fcc", params, county)
    return county or None
