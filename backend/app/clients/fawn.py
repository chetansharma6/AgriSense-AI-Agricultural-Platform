"""FAWN (Florida Automated Weather Network, UF/IFAS) station daily minimum temperatures.

NASA POWER's ~50 km grid misreads Florida's cold nights: on the peninsula the
grid cell includes warm water and reads 2-3 C too warm on freeze nights (it
missed the January 2022 Hastings freeze entirely), while inland North Florida
reads about 1 C too cold. Freezes are therefore counted from the nearest FAWN
station's 2 m daily minimum when one is close enough.

MAX_STATION_KM comes from comparing 41 stations, 2016-2025: a neighbouring
station within 40 km predicts a site's freeze nights per year with a mean error
of 0.3-0.9 nights, against 2.1 for the POWER grid; beyond 40 km it is no better.

Station records are downloaded once and cached; scripts/fetch_fawn.py
pre-fetches every station so the app never waits on FAWN.
"""

import csv
import io
import json
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any, TypedDict

import pandas as pd
import httpx

from app.cache import read_cache, write_cache
from app.clients.http import TIMEOUT_S, http
from app.clients.power import END, START
from app.config import DATA_DIR
from app.utils import haversine_km

REPORT_URL = "https://fawn.ifas.ufl.edu/data/reports/?res"
STATIONS_FILE = DATA_DIR / "fawn_stations.json"
MAX_STATION_KM = 40.0
MIN_YEARS = 5.0  # of complete days, so a new station's short record is not used
COMPLETE_DAY_OBS = 90  # FAWN records every 15 minutes (96 a day)


class Station(TypedDict):
    id: str
    name: str
    lat: float
    lon: float
    years: float  # complete days in START-END, in years


class FawnError(RuntimeError):
    """FAWN returned something other than the expected CSV."""


class FawnTimeout(FawnError):
    """FAWN exceeded its finite request timeout."""


@lru_cache(maxsize=1)
def load_stations() -> tuple[Station, ...]:
    """Stations with a usable record (scripts/fetch_fawn.py writes the file)."""
    if not STATIONS_FILE.exists():
        return ()
    stations: list[Station] = json.loads(STATIONS_FILE.read_text())
    return tuple(s for s in stations if s["years"] >= MIN_YEARS)


def nearest_station(lat: float, lon: float) -> tuple[Station, float] | None:
    """The closest usable station within MAX_STATION_KM, with its distance."""
    candidates = [(haversine_km(lat, lon, s["lat"], s["lon"]), s) for s in load_stations()]
    if not candidates:
        return None
    km, station = min(candidates, key=lambda item: item[0])
    return (station, km) if km <= MAX_STATION_KM else None


def daily_min_c(station_id: str) -> pd.Series:
    """Daily 2 m minimum temperature (C) for complete days in START-END, indexed by date."""
    params = {"station": station_id, "start": START, "end": END}
    cached = read_cache("fawn", params)
    if cached is None:
        cached = _encode(_download(station_id))
        write_cache("fawn", params, cached)
    return _decode(cached)


def _download(station_id: str) -> dict[date, float]:
    start, end = datetime.strptime(START, "%Y%m%d"), datetime.strptime(END, "%Y%m%d")
    form = {
        f"locs__{station_id}": "on", "reportType": "daily", "presetRange": "dates",
        "fromDate_m": start.month, "fromDate_d": start.day, "fromDate_y": start.year,
        "toDate_m": end.month, "toDate_d": end.day, "toDate_y": end.year,
        "vars__AirTemp9": "on", "format": ".CSV (Excel)",
    }
    response = http().post(REPORT_URL, data=form, timeout=TIMEOUT_S)
    try:
        response.raise_for_status()
    except httpx.TimeoutException:
        raise FawnTimeout("FAWN request timed out") from None
    except httpx.HTTPError:
        raise FawnError(f"FAWN HTTP {response.status_code}") from None
    return parse_report(response.text)


def parse_report(text: str) -> dict[date, float]:
    """Daily minimum (C) per complete day from a FAWN daily CSV report."""
    if not text.startswith('"FAWN Station"'):
        # FAWN answers with its HTML form when a station has no data in the range.
        raise FawnError("FAWN report is not a CSV (station has no data for this period?)")
    mins: dict[date, float] = {}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            if int(row["N (# obs)"]) < COMPLETE_DAY_OBS:
                continue
            day = datetime.strptime(row["Period"], "%d %b %Y").date()
            mins[day] = round((float(row["2m T min (F)"]) - 32) * 5 / 9, 2)
        except (KeyError, ValueError):
            continue  # blank or partial row
    return mins


def _encode(mins: dict[date, float]) -> dict[str, Any]:
    """Compact cache form: one value (or null) per day from START."""
    first = datetime.strptime(START, "%Y%m%d").date()
    days = (datetime.strptime(END, "%Y%m%d").date() - first).days + 1
    return {"start": first.isoformat(), "min_c": [mins.get(first + timedelta(days=i)) for i in range(days)]}


def _decode(cached: dict[str, Any]) -> pd.Series:
    index = pd.date_range(cached["start"], periods=len(cached["min_c"]), freq="D")
    return pd.Series(cached["min_c"], index=index, dtype="float64").dropna()
