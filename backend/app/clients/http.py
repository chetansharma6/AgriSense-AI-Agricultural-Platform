"""One shared HTTP client for all data sources, so connections are reused."""

import logging
import threading

import httpx

from app import config

TIMEOUT_S = 30.0

# httpx logs full request URLs at INFO, which would include the NASS key.
logging.getLogger("httpx").setLevel(logging.WARNING)

class OfflineMode(RuntimeError):
    """DEMO_MODE is on, so only cached data can be used."""


_client: httpx.Client | None = None
_client_lock = threading.Lock()


def http() -> httpx.Client:
    """Return the shared client, creating it on first use. Raises OfflineMode
    in DEMO_MODE, which callers turn into null values and a warning."""
    if config.DEMO_MODE:
        raise OfflineMode("DEMO_MODE is on: data not in the cache is unavailable")
    global _client
    with _client_lock:
        if _client is None:
            _client = httpx.Client(timeout=TIMEOUT_S)
    return _client
