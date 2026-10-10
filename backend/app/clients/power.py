"""NASA POWER daily point API: temperature, precipitation and solar.

Fetches a fixed 10-year window so results are stable and cacheable. POWER's
grid is about 0.5 degrees, so coordinates are rounded to 0.1 degree to let
nearby points share one cache entry.
"""

import pandas as pd

from app.cache import read_cache, write_cache
from app.clients.http import http

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
START, END = "20150101", "20241231"
MISSING = -999.0

# POWER parameter -> DataFrame column
PARAMETERS = {
    "T2M": "t_mean_c",
    "T2M_MAX": "t_max_c",
    "T2M_MIN": "t_min_c",
    "PRECTOTCORR": "precip_mm",
    "ALLSKY_SFC_SW_DWN": "solar_kwh_m2",
}


def get_daily_weather(lat: float, lon: float) -> pd.DataFrame:
    """Return daily weather indexed by date, one column per PARAMETERS value.
    Missing values are NaN."""
    params = {"lat": round(lat, 1), "lon": round(lon, 1), "start": START, "end": END}
    series = read_cache("power", params)
    if series is None:
        series = _fetch(params)
        write_cache("power", params, series)
    return _to_frame(series)


def _fetch(params: dict) -> dict[str, dict[str, float]]:
    response = http().get(
        POWER_URL,
        params={
            "parameters": ",".join(PARAMETERS),
            "community": "AG",
            "latitude": params["lat"],
            "longitude": params["lon"],
            "start": params["start"],
            "end": params["end"],
            "format": "JSON",
        },
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()["properties"]["parameter"]


def _to_frame(series: dict[str, dict[str, float]]) -> pd.DataFrame:
    frame = pd.DataFrame(series).rename(columns=PARAMETERS)
    frame.index = pd.to_datetime(frame.index, format="%Y%m%d")
    return frame.replace(MISSING, float("nan")).sort_index()
