"""USDA NASS Quick Stats client with a disk cache.

Every query is cached by its params (the key is never part of the cache
name), so each distinct query hits NASS once. One shared HTTP client keeps
connections open between calls.
"""

import logging
from typing import Any

import httpx

from app.cache import read_cache, write_cache
from app.config import nass_api_key

NASS_URL = "https://quickstats.nass.usda.gov/api/api_GET/"
TIMEOUT_S = 30.0

# httpx logs full request URLs at INFO, which would include the key.
logging.getLogger("httpx").setLevel(logging.WARNING)

_client: httpx.Client | None = None


def _http() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=TIMEOUT_S)
    return _client


def query(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Return Quick Stats rows for the params. Empty list if NASS has none."""
    cached = read_cache("nass", params)
    if cached is not None:
        return cached

    response = _http().get(NASS_URL, params={**params, "key": nass_api_key(), "format": "JSON"})
    if response.status_code == 400 and "no data" in response.text.lower():
        rows: list[dict[str, Any]] = []
    else:
        response.raise_for_status()
        rows = response.json().get("data", [])

    write_cache("nass", params, rows)
    return rows
