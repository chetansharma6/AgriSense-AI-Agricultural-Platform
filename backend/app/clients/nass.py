"""USDA NASS Quick Stats client with a disk cache.

Every query is cached by its params (the key is never part of the cache
name), so each distinct query hits NASS once.
"""

from typing import Any

from app.cache import read_cache, write_cache
from app.clients.http import http
from app.config import nass_api_key

NASS_URL = "https://quickstats.nass.usda.gov/api/api_GET/"


# Quick Stats rows have ~40 fields; only these are kept (and cached).
KEEP_FIELDS = (
    "short_desc", "commodity_desc", "class_desc", "statisticcat_desc", "domain_desc",
    "agg_level_desc", "source_desc", "reference_period_desc", "year", "Value",
    "county_name", "county_ansi",
)


class NassError(RuntimeError):
    """A NASS request failed. The message never contains the API key."""


def query(params: dict[str, Any], invalid_means_empty: bool = False) -> list[dict[str, Any]]:
    """Return Quick Stats rows for the params. Empty list if NASS has none.

    NASS answers "invalid query" (not "no data") when a filter value never
    occurs with the others, e.g. county yields for a county with no survey
    crops. Pass invalid_means_empty=True for such queries.
    """
    cached = read_cache("nass", params)
    if cached is not None:
        return cached

    response = http().get(NASS_URL, params={**params, "key": nass_api_key(), "format": "JSON"})
    if response.status_code == 200:
        rows: list[dict[str, Any]] = [
            {field: row[field] for field in KEEP_FIELDS if field in row} for row in response.json().get("data", [])
        ]
    elif response.status_code == 400 and _is_empty_answer(response.text, invalid_means_empty):
        rows = []
    else:
        # Never raise httpx's own error: its message contains the URL and key.
        raise NassError(f"NASS request failed ({response.status_code}): {response.text[:200]}")

    write_cache("nass", params, rows)
    return rows


def _is_empty_answer(text: str, invalid_means_empty: bool) -> bool:
    text = text.lower()
    return "no data" in text or (invalid_means_empty and "invalid query" in text)
