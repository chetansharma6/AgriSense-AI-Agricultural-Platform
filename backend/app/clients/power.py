"""NASA POWER daily point API: temperature and precipitation.

Fetches a fixed 10-year window so results are stable and cacheable. POWER's
grid is about 0.5 degrees, so coordinates are rounded to 0.1 degree to let
nearby points share one cache entry.
"""

import httpx
import pandas as pd
import time

from app.cache import read_cache, write_cache
from app.clients.http import http

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
START, END = "20160101", "20251231"
TIMEOUT_S = 90.0
MISSING = -999.0


class PowerError(RuntimeError):
    """NASA POWER returned an HTTP, empty, or malformed response."""


def _valid_series(value: object) -> bool:
    return isinstance(value, dict) and all(isinstance(series, dict) for series in value.values())

# POWER parameter -> DataFrame column
PARAMETERS = {
    "T2M": "t_mean_c",
    "T2M_MAX": "t_max_c",
    "T2M_MIN": "t_min_c",
    "PRECTOTCORR": "precip_mm",
}


def get_daily_weather(lat: float, lon: float) -> pd.DataFrame:
    """Return daily weather indexed by date, one column per PARAMETERS value.
    Missing values are NaN."""
    params = {"lat": round(lat, 1), "lon": round(lon, 1), "start": START, "end": END}
    series = read_cache("power", params, _valid_series)
    if series is None:
        series = _fetch(params)
        write_cache("power", params, series)
    return _to_frame(series)


def _fetch(params: dict) -> dict[str, dict[str, float]]:
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
            response = http().get(POWER_URL, params=query, timeout=TIMEOUT_S)
        except httpx.TimeoutException:
            if attempt == 2:
                raise
            time.sleep(0.05)
            continue
        if response.status_code >= 500 and attempt == 1:
            time.sleep(0.05)
            continue
        try:
            response.raise_for_status()
            parameters = response.json()["properties"]["parameter"]
            if not isinstance(parameters, dict) or not parameters:
                raise ValueError("parameter data is empty")
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
