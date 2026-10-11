"""One shared HTTP client for all data sources, so connections are reused."""

import logging
import threading
import time

import httpx


TIMEOUT_S = 30.0

# httpx logs full request URLs at INFO, which would include the NASS key.
logging.getLogger("httpx").setLevel(logging.WARNING)

_client: httpx.Client | None = None
_client_lock = threading.Lock()


def http() -> httpx.Client:
    """Return the shared client, creating it on first use."""
    global _client
    with _client_lock:
        if _client is None:
            _client = httpx.Client(timeout=TIMEOUT_S)
    return _client


def timeout_for(deadline: float | None, maximum: float = TIMEOUT_S) -> float:
    """Return a finite provider timeout without exceeding a request deadline."""
    if deadline is None:
        return maximum
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise httpx.TimeoutException("recommendation deadline expired")
    return min(maximum, remaining)
