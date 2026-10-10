"""Builds API responses: gathers sources in parallel, then scores every crop.

A failed source never fails the request: its values become null and a
message is added to warnings. Complete responses are kept in a small
in-memory cache (on top of the per-source disk caches), so repeat requests
for the same spot skip all I/O and scoring.
"""

import copy
import json
import logging
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor, wait
from functools import lru_cache
from typing import Any, Callable, TypeVar

from app import config
from app.climate import summarize, with_station_minimums
from app.clients import fawn
from app.clients.fcc import lookup_county
from app.clients.power import get_daily_weather
from app.clients.soil import SoilNotFound, get_soil
from app.crops import load_crops
from app.market import load_market
from app.scoring import rank_crops, score_crop, scoring_rules
from app.utils import haversine_km

T = TypeVar("T")

log = logging.getLogger(__name__)

RESPONSE_CACHE_SIZE = 256
RESPONSE_CACHE_TTL_S = 3600.0
FACTOR_COUNT = 6
_response_cache: OrderedDict[tuple[float, float], tuple[float, dict[str, Any]]] = OrderedDict()
_response_cache_lock = threading.Lock()

SOIL_FIELDS = ("soil_ph", "organic_matter_pct", "sand_pct", "clay_pct", "texture", "drainage")
CLIMATE_FIELDS = ("annual_precip_mm", "frost_free_days", "last_spring_frost", "first_fall_frost",
                  "avg_summer_high_c", "avg_winter_low_c")


class OutsideFlorida(ValueError):
    """The point is not in Florida."""


class SourcesTooSlow(RuntimeError):
    """DEMO_MODE: live data missed the deadline and no demo farm is close enough."""


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
    if config.DEMO_MODE:
        exact = _exact_demo_response(lat, lon)
        if exact is not None:
            return exact
    key = _cache_key(lat, lon)
    now = time.monotonic()
    with _response_cache_lock:
        hit = _response_cache.get(key)
        if hit is not None and now - hit[0] < RESPONSE_CACHE_TTL_S:
            _response_cache.move_to_end(key)
            log.info("recommend %s: memory cache hit", key)
            return _with_location(copy.deepcopy(hit[1]), lat, lon)

    started = time.perf_counter()
    if config.DEMO_MODE:
        result, complete = _build_with_deadline(lat, lon)
    else:
        result, complete = _build_recommendation(lat, lon)
    log.info("recommend %s: answered in %.0f ms%s", key, (time.perf_counter() - started) * 1000,
             "" if complete else " (incomplete; not cached)")
    if complete:  # never pin a degraded answer: the next request retries the failed source
        _remember(key, result)
    return result


def _remember(key: tuple[float, float], result: dict[str, Any]) -> None:
    with _response_cache_lock:
        _response_cache[key] = (time.monotonic(), copy.deepcopy(result))
        _response_cache.move_to_end(key)
        while len(_response_cache) > RESPONSE_CACHE_SIZE:
            _response_cache.popitem(last=False)


def _build_with_deadline(lat: float, lon: float) -> tuple[dict[str, Any], bool]:
    """Use saved data nearby; otherwise return bounded live/partial data."""
    fallback = _demo_fallback(lat, lon, "DEMO_MODE uses the saved demo response")
    if fallback is not None:
        return fallback, False
    return _build_recommendation_bounded(lat, lon, config.DEMO_DEADLINE_S)


def _bounded_fetches(fetches: dict[str, Callable[[], Any]], timeout_s: float,
                    warnings: list[str], failed: list[str]) -> dict[str, Any | None]:
    """Fetch independent providers without letting one occupy the request."""
    pool = ThreadPoolExecutor(max_workers=len(fetches), thread_name_prefix="bounded_source")
    futures: dict[str, Future[Any]] = {
        name: pool.submit(_attempt, fetch, name, warnings, failed)
        for name, fetch in fetches.items()
    }
    done, pending = wait(futures.values(), timeout=max(timeout_s, 0.0))
    for name, future in futures.items():
        if future in pending:
            failed.append(name)
            warnings.append(f"{name} timed out; related values are null")
    results = {name: (future.result() if future in done else None)
               for name, future in futures.items()}
    # A timed-out provider may still be inside an upstream HTTP call. Do not
    # wait for it and do not reuse its worker for another request.
    pool.shutdown(wait=False, cancel_futures=True)
    return results


def _build_recommendation_bounded(lat: float, lon: float, timeout_s: float) -> tuple[dict[str, Any], bool]:
    """Build a valid live response within the demo deadline, allowing nulls."""
    started = time.perf_counter()
    warnings: list[str] = []
    failed: list[str] = []
    station = fawn.nearest_station(lat, lon)
    source_names = {
        "County lookup (FCC)": lambda: lookup_county(lat, lon),
        "Soil data (USDA SSURGO)": lambda: get_soil(lat, lon),
        "Weather data (NASA POWER)": lambda: get_daily_weather(lat, lon),
    }
    if station:
        source_names["Freeze records (FAWN station)"] = lambda: fawn.daily_min_c(station[0]["id"])
    results = _bounded_fetches(source_names, timeout_s, warnings, failed)
    county = results.get("County lookup (FCC)")
    soil = results.get("Soil data (USDA SSURGO)")
    weather = results.get("Weather data (NASA POWER)")
    station_min = results.get("Freeze records (FAWN station)")
    if weather is not None and station_min is not None and station is not None:
        weather = with_station_minimums(weather, station_min)
    if county is not None and county["state"] != "FL":
        raise OutsideFlorida
    if soil is not None and soil["soil_ph"] is None:
        warnings.append("Soil survey reports no pH for this soil; the pH factor is skipped")

    remaining = timeout_s - (time.perf_counter() - started)
    market = None
    if county is not None and remaining > 0:
        market_result = _bounded_fetches(
            {"Yield and price data (USDA NASS)": lambda: load_market(county["county_fips"])},
            remaining, warnings, failed)
        market = market_result["Yield and price data (USDA NASS)"]
    climate = _attempt(lambda: summarize(weather), "Climate summary", warnings, failed) if weather is not None else None
    conditions = {field: (soil or {}).get(field) for field in SOIL_FIELDS}
    conditions.update({field: (climate or {}).get(field) for field in CLIMATE_FIELDS})
    crops = rank_crops([score_crop(crop, soil, weather, market) for crop in load_crops().values()])
    response = {
        "location": {"lat": lat, "lon": lon,
                     "county": county["county"] if county else None,
                     "county_fips": county["county_fips"] if county else None,
                     "state": "FL"},
        "conditions": conditions, "crops": crops, "warnings": warnings,
        "scoring": scoring_rules(), "provenance": _provenance("live"),
        "confidence": _confidence({"crops": crops, "warnings": warnings}),
    }
    return response, not failed


def _demo_fallback(lat: float, lon: float, reason: str) -> dict[str, Any] | None:
    """The nearest demo farm's saved response with a warning, or None if none is close."""
    farm, distance = min(((name, haversine_km(lat, lon, *point)) for name, point in config.DEMO_FARMS.items()),
                         key=lambda item: item[1])
    if distance > config.DEMO_FALLBACK_KM:
        log.warning("recommend (%.4f, %.4f): %s; nearest demo farm %s is %.0f km away, no fallback",
                    lat, lon, reason, farm, distance)
        return None
    log.warning("recommend (%.4f, %.4f): %s; serving demo data for %s (%.1f km away)",
                lat, lon, reason, farm, distance)
    response = copy.deepcopy(_demo_response(farm))
    name = farm.replace("_", " ").title()
    response["warnings"].insert(0, f"Showing cached data for {name} ({reason})")
    response["provenance"] = _provenance("demo", "Fallback saved response")
    response["confidence"] = _confidence(response)
    return response


def _exact_demo_response(lat: float, lon: float) -> dict[str, Any] | None:
    """Serve committed demo data immediately for an official demo coordinate."""
    for farm, point in config.DEMO_FARMS.items():
        if (lat, lon) == point:
            response = copy.deepcopy(_demo_response(farm))
            response["provenance"] = _provenance("demo", f"Saved {farm.replace('_', ' ').title()} response")
            response["confidence"] = _confidence(response)
            return response
    return None


def _provenance(mode: str, detail: str | None = None) -> dict[str, Any]:
    sources = [
        {"name": "USDA SSURGO", "status": "saved" if mode == "demo" else "live", "detail": detail},
        {"name": "NASA POWER", "status": "saved" if mode == "demo" else "live", "detail": detail},
        {"name": "USDA NASS", "status": "saved" if mode == "demo" else "live", "detail": detail},
        {"name": "UF/IFAS FAWN", "status": "saved" if mode == "demo" else "live", "detail": detail},
    ]
    return {"mode": mode, "sources": sources}


def _confidence(response: dict[str, Any]) -> dict[str, Any]:
    factors = [factor for crop in response.get("crops", []) for factor in crop.get("factors", {}).values()]
    available = round(sum(value is not None for value in factors) / max(len(factors), 1) * FACTOR_COUNT)
    level = "high" if available >= 5 else "medium" if available >= 3 else "low"
    notes = []
    if response.get("warnings"):
        notes.append("One or more data sources reported a warning")
    return {"level": level, "available_factors": available, "total_factors": FACTOR_COUNT, "notes": notes}


@lru_cache(maxsize=None)
def _demo_response(farm: str) -> dict[str, Any]:
    return json.loads((config.DATA_DIR / "demo" / f"{farm}.json").read_text())["recommend"]


def _with_location(result: dict[str, Any], lat: float, lon: float) -> dict[str, Any]:
    """A cached answer echoes this request's coordinates, not the first one's."""
    result["location"]["lat"], result["location"]["lon"] = lat, lon
    return result


def _build_recommendation(lat: float, lon: float) -> tuple[dict[str, Any], bool]:
    """The response, and whether every source answered."""
    warnings: list[str] = []
    failed: list[str] = []
    # Avoid nesting a thread pool inside the DEMO_MODE deadline worker. This
    # keeps the synchronous ASGI test client and constrained free hosts from
    # deadlocking while retaining parallel source fetches for normal requests.
    if threading.current_thread().name.startswith("recommend_"):
        return _build_recommendation_sequential(lat, lon, warnings, failed)
    with ThreadPoolExecutor(max_workers=4) as pool:
        county_job = pool.submit(_attempt, lambda: lookup_county(lat, lon), "County lookup (FCC)", warnings, failed)
        soil_job = pool.submit(_attempt, lambda: get_soil(lat, lon), "Soil data (USDA SSURGO)", warnings, failed)
        weather_job = pool.submit(_attempt, lambda: get_daily_weather(lat, lon), "Weather data (NASA POWER)",
                                  warnings, failed)
        station = fawn.nearest_station(lat, lon)
        station_job = (pool.submit(_attempt, lambda: fawn.daily_min_c(station[0]["id"]),
                                   "Freeze records (FAWN station)", warnings, failed) if station else None)
        county, soil, weather = county_job.result(), soil_job.result(), weather_job.result()
        station_min = station_job.result() if station_job else None
    if weather is not None and station_min is not None and station is not None:
        weather = with_station_minimums(weather, station_min)
        log.info("freezes from FAWN %s (%.0f km away)", station[0]["name"], station[1])

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
    response["provenance"] = _provenance("live")
    response["confidence"] = _confidence(response)
    return response, not failed


def _build_recommendation_sequential(lat: float, lon: float, warnings: list[str],
                                     failed: list[str]) -> tuple[dict[str, Any], bool]:
    """Build a deadline-worker response without recursively creating pools."""
    county = _attempt(lambda: lookup_county(lat, lon), "County lookup (FCC)", warnings, failed)
    soil = _attempt(lambda: get_soil(lat, lon), "Soil data (USDA SSURGO)", warnings, failed)
    weather = _attempt(lambda: get_daily_weather(lat, lon), "Weather data (NASA POWER)", warnings, failed)
    station = fawn.nearest_station(lat, lon)
    station_min = (_attempt(lambda: fawn.daily_min_c(station[0]["id"]), "Freeze records (FAWN station)", warnings, failed)
                   if station else None)
    if weather is not None and station_min is not None and station is not None:
        weather = with_station_minimums(weather, station_min)
    fcc_failed = "County lookup (FCC)" in failed
    if county is None and not fcc_failed:
        raise OutsideFlorida
    if county is not None and county["state"] != "FL":
        raise OutsideFlorida
    if soil is not None and soil["soil_ph"] is None:
        warnings.append("Soil survey reports no pH for this soil; the pH factor is skipped")
    market = _attempt(lambda: load_market(county["county_fips"] if county else None),
                      "Yield and price data (USDA NASS)", warnings, failed)
    climate = _attempt(lambda: summarize(weather), "Climate summary", warnings, failed) if weather is not None else None
    conditions = {field: (soil or {}).get(field) for field in SOIL_FIELDS}
    conditions.update({field: (climate or {}).get(field) for field in CLIMATE_FIELDS})
    crops = rank_crops([score_crop(crop, soil, weather, market) for crop in load_crops().values()])
    response = {"location": {"lat": lat, "lon": lon, "county": county["county"] if county else None,
                              "county_fips": county["county_fips"] if county else None, "state": "FL"},
                "conditions": conditions, "crops": crops, "warnings": warnings,
                "scoring": scoring_rules(), "provenance": _provenance("live"),
                "confidence": _confidence({"crops": crops, "warnings": warnings})}
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
