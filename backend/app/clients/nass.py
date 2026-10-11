"""USDA NASS Quick Stats client with a disk cache.

Every query is cached by its params (the key is never part of the cache
name), so each distinct query hits NASS once.
"""

import re
import math
from typing import Any

import httpx

from app.cache import read_cache, write_cache
from app.clients.http import TIMEOUT_S, http, timeout_for
from app.config import nass_api_key

NASS_URL = "https://quickstats.nass.usda.gov/api/api_GET/"


def _valid_rows(value: Any) -> bool:
    """NASS rows must retain the fields consumed by market aggregation."""
    required = {"short_desc", "statisticcat_desc", "domain_desc", "agg_level_desc",
                "reference_period_desc", "year", "Value"}
    if not isinstance(value, list):
        return False
    for row in value:
        if not isinstance(row, dict) or not required.issubset(row):
            return False
        if not all(isinstance(row[key], str) and row[key].strip()
                   for key in required - {"year"}):
            return False
        try:
            year = int(row["year"])
        except (TypeError, ValueError):
            return False
        if not 1900 <= year <= 2100:
            return False
        # Value can be a documented withheld marker, but never a non-finite number.
        cleaned = row["Value"].replace(",", "").strip()
        if cleaned and cleaned[0] != "(":
            try:
                if not math.isfinite(float(cleaned)):
                    return False
            except ValueError:
                return False
    return True


# Quick Stats rows have ~40 fields; only these are kept (and cached).
KEEP_FIELDS = (
    "short_desc", "commodity_desc", "class_desc", "statisticcat_desc", "domain_desc",
    "agg_level_desc", "source_desc", "reference_period_desc", "year", "Value",
    "county_name", "county_ansi",
)


class NassError(RuntimeError):
    """A NASS request failed. The message never contains the API key."""


def _safe_error(text: str) -> str:
    """Keep provider diagnostics useful without echoing credential-shaped data."""
    return re.sub(r"(?i)(api[_-]?key|key|token|secret)([=:][^&\s]+)", r"\1=[redacted]", text[:200])


def query(params: dict[str, Any], invalid_means_empty: bool = False,
          *, deadline: float | None = None) -> list[dict[str, Any]]:
    """Return Quick Stats rows for the params. Empty list if NASS has none.

    NASS answers "invalid query" (not "no data") when a filter value never
    occurs with the others, e.g. county yields for a county with no survey
    crops. Pass invalid_means_empty=True for such queries.
    """
    cached = read_cache("nass", params, _valid_rows)
    if cached is not None:
        return cached

    try:
        response = http().get(
            NASS_URL,
            params={**params, "key": nass_api_key(), "format": "JSON"},
            timeout=timeout_for(deadline, TIMEOUT_S),
        )
    except httpx.TimeoutException:
        raise NassError("NASS request timed out") from None
    except httpx.HTTPError:
        raise NassError("NASS request failed") from None
    if response.status_code == 200:
        try:
            payload = response.json()
            data = payload.get("data", [])
            if not isinstance(data, list):
                raise TypeError("data is not a list")
            rows: list[dict[str, Any]] = [
                {field: row[field] for field in KEEP_FIELDS if field in row}
                for row in data if isinstance(row, dict)
            ]
        except (TypeError, ValueError, KeyError):
            raise NassError("NASS response malformed") from None
    elif response.status_code == 400 and _is_empty_answer(response.text, invalid_means_empty):
        rows = []
    else:
        # Never raise httpx's own error: its message contains the URL and key.
        raise NassError(f"NASS request failed ({response.status_code}): {_safe_error(response.text)}")

    write_cache("nass", params, rows, _valid_rows)
    return rows


def _is_empty_answer(text: str, invalid_means_empty: bool) -> bool:
    text = text.lower()
    return "no data" in text or (invalid_means_empty and "invalid query" in text)
