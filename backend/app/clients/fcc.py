"""FCC Census Area API: lat/lon -> county name and FIPS code."""

from typing import TypedDict

import httpx

from app.cache import read_cache, write_cache
from app.clients.http import TIMEOUT_S, http, timeout_for

FCC_URL = "https://geo.fcc.gov/api/census/area"


class County(TypedDict):
    county: str
    county_fips: str
    state: str


class FccError(RuntimeError):
    """FCC returned an HTTP or malformed response."""


class FccTimeout(FccError):
    """FCC exceeded its finite request timeout."""


def _valid_county(value: object) -> bool:
    return value == {} or (isinstance(value, dict)
                           and all(isinstance(value.get(key), str) for key in ("county", "county_fips", "state")))


def lookup_county(lat: float, lon: float, *, deadline: float | None = None) -> County | None:
    """Return the county for a point, or None if the point is not in a county."""
    params = {"lat": round(lat, 4), "lon": round(lon, 4)}
    cached = read_cache("fcc", params, _valid_county)
    if cached is not None:
        return cached or None

    try:
        response = http().get(FCC_URL, params={**params, "format": "json"},
                              timeout=timeout_for(deadline, TIMEOUT_S))
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", [])
        if not isinstance(results, list):
            raise TypeError("results is not a list")
    except httpx.TimeoutException:
        raise FccTimeout("FCC request timed out") from None
    except (httpx.HTTPError, TypeError, ValueError, AttributeError) as error:
        raise FccError(f"FCC response unavailable ({type(error).__name__})") from None
    county: County | dict = {}
    if results:
        try:
            first = results[0]
            county = {"county": first["county_name"].removesuffix(" County"),
                      "county_fips": first["county_fips"], "state": first["state_code"]}
        except (KeyError, AttributeError, TypeError):
            raise FccError("FCC response malformed") from None
    write_cache("fcc", params, county)
    return county or None
