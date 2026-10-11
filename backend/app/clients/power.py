"""NASA POWER daily point API: temperature and precipitation.

Fetches a fixed 10-year window so results are stable and cacheable. POWER's
grid is about 0.5 degrees, so coordinates are rounded to 0.1 degree to let
nearby points share one cache entry.
"""

import httpx
import pandas as pd
import time
import math
from datetime import datetime, timedelta
from functools import lru_cache

from app.cache import read_cache, write_cache
from app.clients.http import http, timeout_for

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
START, END = "20160101", "20251231"
TIMEOUT_S = 90.0
MISSING = -999.0


class PowerError(RuntimeError):
    """NASA POWER returned an HTTP, empty, or malformed response."""


@lru_cache(maxsize=4)
def _expected_days(start: str, end: str) -> frozenset[str]:
    first = datetime.strptime(start, "%Y%m%d")
    count = (datetime.strptime(end, "%Y%m%d") - first).days + 1
    return frozenset((first + timedelta(days=i)).strftime("%Y%m%d") for i in range(count))


def _valid_series(value: object) -> bool:
    """Accept only complete, finite daily parameter maps for the fixed window."""
    if not isinstance(value, dict) or set(value) != set(PARAMETERS):
        return False
    expected = _expected_days(START, END)
    for series in value.values():
        if not isinstance(series, dict) or series.keys() != expected:
            return False
        for number in series.values():
            if not (isinstance(number, (int, float)) and not isinstance(number, bool)
                    and math.isfinite(number)):
                return False
    return True

# POWER parameter -> DataFrame column
PARAMETERS = {
    "T2M": "t_mean_c",
    "T2M_MAX": "t_max_c",
    "T2M_MIN": "t_min_c",
    "PRECTOTCORR": "precip_mm",
}


def get_daily_weather(lat: float, lon: float, *, deadline: float | None = None) -> pd.DataFrame:
    """Return daily weather indexed by date, one column per PARAMETERS value.
    Missing values are NaN."""
    params = {"lat": round(lat, 1), "lon": round(lon, 1), "start": START, "end": END}
    series = read_cache("power", params, _valid_series)
    if series is None:
        series = _fetch(params, deadline=deadline)
        write_cache("power", params, series, _valid_series)
    return _to_frame(series)


def _fetch(params: dict, *, deadline: float | None = None) -> dict[str, dict[str, float]]:
    """One POWER request, retried once on a timeout or a 5xx response."""
    query = {
        "parameters": ",".join(PARAMETERS),
        "community": "AG",
        "latitude": params["lat"],
        "longitude": params["lon"],
        "start": params["start"],
        "end": params["end"],
        "format": "JSON",
    }
    for attempt in (1, 2):
        try:
            response = http().get(POWER_URL, params=query, timeout=timeout_for(deadline, TIMEOUT_S))
        except httpx.TimeoutException:
            if attempt == 2 or (deadline is not None and deadline - time.monotonic() <= 0.1):
                raise
            time.sleep(0.05)
            continue
        except httpx.HTTPError:
            raise PowerError("NASA POWER request failed") from None
        if response.status_code >= 500 and attempt == 1 and (deadline is None or deadline - time.monotonic() > 0.1):
            time.sleep(0.05)
            continue
        try:
            response.raise_for_status()
            parameters = response.json()["properties"]["parameter"]
            if not _valid_series(parameters):
                raise ValueError("parameter data is incomplete or invalid")
            return parameters
        except httpx.HTTPStatusError:
            raise PowerError(f"NASA POWER HTTP {response.status_code}") from None
        except (KeyError, TypeError, ValueError):
            raise PowerError("NASA POWER response malformed or empty") from None
    raise AssertionError("unreachable")


def _to_frame(series: dict[str, dict[str, float]]) -> pd.DataFrame:
    frame = pd.DataFrame(series).rename(columns=PARAMETERS)
    frame.index = pd.to_datetime(frame.index, format="%Y%m%d")
    return frame.replace(MISSING, float("nan")).sort_index()
