"""Builds API responses: gathers sources in parallel, then scores every crop.

A failed source never fails the request: its values become null and a
message is added to warnings. Complete responses are kept in a small
in-memory cache (on top of the per-source disk caches), so repeat requests
for the same spot skip all I/O and scoring.
"""

import copy
import logging
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

from app.climate import summarize
from app.clients.fcc import lookup_county
from app.clients.power import get_daily_weather
from app.clients.soil import SoilNotFound, get_soil
from app.crops import load_crops
from app.market import load_market
from app.scoring import rank_crops, score_crop, scoring_rules

T = TypeVar("T")

log = logging.getLogger(__name__)

RESPONSE_CACHE_SIZE = 256
RESPONSE_CACHE_TTL_S = 3600.0
_response_cache: OrderedDict[tuple[float, float], tuple[float, dict[str, Any]]] = OrderedDict()
_response_cache_lock = threading.Lock()

SOIL_FIELDS = ("soil_ph", "organic_matter_pct", "sand_pct", "clay_pct", "texture", "drainage")
CLIMATE_FIELDS = ("annual_precip_mm", "frost_free_days", "last_spring_frost", "first_fall_frost",
                  "avg_summer_high_c", "avg_winter_low_c")


class OutsideFlorida(ValueError):
    """The point is not in Florida."""


def _attempt(fetch: Callable[[], T], source: str, warnings: list[str], failed: list[str]) -> T | None:
    """Run one source, log how long it took, and turn a failure into a warning."""
    started = time.perf_counter()
    outcome = "ok"
    try:
        return fetch()
    except SoilNotFound as error:
        outcome = "no data"
        warnings.append(f"{error}; soil values are null")
        return None
    except Exception as error:  # any source failure becomes a warning
        outcome = f"failed ({type(error).__name__})"
        failed.append(source)
        warnings.append(f"{source} unavailable ({type(error).__name__}); related values are null")
        return None
    finally:
        log.info("%s: %s in %.0f ms", source, outcome, (time.perf_counter() - started) * 1000)


def _cache_key(lat: float, lon: float) -> tuple[float, float]:
    # Same rounding as the FCC and soil caches (about 11 m).
    return round(lat, 4), round(lon, 4)


def clear_response_cache() -> None:
    with _response_cache_lock:
        _response_cache.clear()


def recommend(lat: float, lon: float) -> dict[str, Any]:
    """Full /api/recommend response for a Florida point, from memory when possible."""
    key = _cache_key(lat, lon)
    now = time.monotonic()
    with _response_cache_lock:
        hit = _response_cache.get(key)
        if hit is not None and now - hit[0] < RESPONSE_CACHE_TTL_S:
            _response_cache.move_to_end(key)
            log.info("recommend %s: memory cache hit", key)
            return _with_location(copy.deepcopy(hit[1]), lat, lon)

    started = time.perf_counter()
    result, complete = _build_recommendation(lat, lon)
    log.info("recommend %s: built in %.0f ms%s", key, (time.perf_counter() - started) * 1000,
             "" if complete else " (a source failed; not cached)")
    if complete:  # never pin a degraded answer: the next request retries the failed source
        with _response_cache_lock:
            _response_cache[key] = (now, copy.deepcopy(result))
            _response_cache.move_to_end(key)
            while len(_response_cache) > RESPONSE_CACHE_SIZE:
                _response_cache.popitem(last=False)
    return result


def _with_location(result: dict[str, Any], lat: float, lon: float) -> dict[str, Any]:
    """A cached answer echoes this request's coordinates, not the first one's."""
    result["location"]["lat"], result["location"]["lon"] = lat, lon
    return result


def _build_recommendation(lat: float, lon: float) -> tuple[dict[str, Any], bool]:
    """The response, and whether every source answered."""
    warnings: list[str] = []
    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        county_job = pool.submit(_attempt, lambda: lookup_county(lat, lon), "County lookup (FCC)", warnings, failed)
        soil_job = pool.submit(_attempt, lambda: get_soil(lat, lon), "Soil data (USDA SSURGO)", warnings, failed)
        weather_job = pool.submit(_attempt, lambda: get_daily_weather(lat, lon), "Weather data (NASA POWER)",
                                  warnings, failed)
        county, soil, weather = county_job.result(), soil_job.result(), weather_job.result()

    fcc_failed = "County lookup (FCC)" in failed
    # FCC answered but found no county: open water beyond Florida's county lines.
    if county is None and not fcc_failed:
        raise OutsideFlorida
    if county is not None and county["state"] != "FL":
        raise OutsideFlorida
    if soil is not None and soil["soil_ph"] is None:
        warnings.append("Soil survey reports no pH for this soil; the pH factor is skipped")

    market = _attempt(lambda: load_market(county["county_fips"] if county else None),
                      "Yield and price data (USDA NASS)", warnings, failed)

    climate = (_attempt(lambda: summarize(weather), "Climate summary", warnings, failed)
               if weather is not None else None)
    conditions = {field: (soil or {}).get(field) for field in SOIL_FIELDS}
    conditions.update({field: (climate or {}).get(field) for field in CLIMATE_FIELDS})

    crops = rank_crops([score_crop(crop, soil, weather, market) for crop in load_crops().values()])

    response = {
        "location": {
            "lat": lat,
            "lon": lon,
            "county": county["county"] if county else None,
            "county_fips": county["county_fips"] if county else None,
            "state": "FL",
        },
        "conditions": conditions,
        "crops": crops,
        "warnings": warnings,
        "scoring": scoring_rules(),
    }
    return response, not failed


def crop_detail(crop_id: str, lat: float, lon: float) -> dict[str, Any] | None:
    """/api/crops/{crop_id} response, or None for an unknown crop id."""
    crop = load_crops().get(crop_id)
    if crop is None:
        return None
    result = recommend(lat, lon)
    scored = next(item for item in result["crops"] if item["id"] == crop_id)
    return {
        **scored,
        "requirements": crop.requirements(),
        "general_guidance": crop.general_guidance,
        "extension_links": [link.model_dump() for link in crop.extension_links],
        "conditions": result["conditions"],
        "location": result["location"],
        "scoring": result["scoring"],
    }
