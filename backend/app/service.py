"""Builds API responses: gathers sources in parallel, then scores every crop.

A failed source never fails the request: its values become null and a
message is added to warnings. Complete responses are kept in a small
in-memory cache (on top of the per-source disk caches), so repeat requests
for the same spot skip all I/O and scoring.
"""

import copy
import inspect
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
from app.scoring import climate_risk_notes, estimated_gross_value, rank_crops, scale_adjusted_score, scale_info, score_crop, scoring_rules
from app.utils import haversine_km

T = TypeVar("T")

log = logging.getLogger(__name__)

RESPONSE_CACHE_SIZE = 256
RESPONSE_CACHE_TTL_S = 3600.0
MAX_CONCURRENT_RECOMMENDATIONS = 8
MAX_CONCURRENT_PROVIDER_WORK = 8
FACTOR_COUNT = 6
_response_cache: OrderedDict[tuple[float, float], tuple[float, dict[str, Any]]] = OrderedDict()
_response_cache_lock = threading.Lock()
_recommendation_slots = threading.BoundedSemaphore(MAX_CONCURRENT_RECOMMENDATIONS)
_provider_pool = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_PROVIDER_WORK,
                                    thread_name_prefix="provider")
_inflight: dict[tuple[float, float], Future[tuple[dict[str, Any], bool]]] = {}
_inflight_lock = threading.Lock()
# A single fixed pool bounds active provider work even when callers time out.
# Pending jobs are cancelled below; running HTTP calls retain their own provider
# timeout, but cannot create additional threads or executor instances.
_provider_pool = ThreadPoolExecutor(
    max_workers=MAX_CONCURRENT_PROVIDER_WORK, thread_name_prefix="provider"
)

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
    with _inflight_lock:
        _inflight.clear()


def recommend(lat: float, lon: float, acres: float | None = None) -> dict[str, Any]:
    """Build a recommendation while bounding expensive concurrent work."""
    if not _recommendation_slots.acquire(blocking=False):
        raise SourcesTooSlow("Too many recommendation requests are in progress")
    try:
        return _recommend(lat, lon, acres)
    finally:
        _recommendation_slots.release()


def _recommend(lat: float, lon: float, acres: float | None = None) -> dict[str, Any]:
    """Full /api/recommend response for a Florida point, from memory when possible."""
    if config.DEMO_MODE:
        exact = _exact_demo_response(lat, lon)
        if exact is not None:
            exact = _apply_acres(exact, acres)
            exact["confidence"] = _confidence(exact, "demo")
            return exact
    key = _cache_key(lat, lon)
    now = time.monotonic()
    with _response_cache_lock:
        hit = _response_cache.get(key)
        if hit is not None and now - hit[0] < RESPONSE_CACHE_TTL_S:
            _response_cache.move_to_end(key)
            log.info("recommend %s: memory cache hit", key)
            cached = _with_location(_apply_acres(copy.deepcopy(hit[1]), acres), lat, lon)
            cached["provenance"] = _provenance("live", detail="Memory cache", cache_status="cached")
            cached["confidence"] = _confidence(cached, "cached")
            return cached

    started = time.perf_counter()
    deadline = started + config.RECOMMENDATION_DEADLINE_S
    result, complete = _coalesced_build(key, lat, lon, deadline)
    if complete:
        _remember(key, result)  # Cache location scores before request-specific land-size caps.
    # Normalize live and partial responses through the same response decoration
    # used by saved/demo data, without changing any score calculation.
    result = _apply_acres(result, acres)
    result["confidence"] = _confidence(result, "live")
    log.info("recommend %s: answered in %.0f ms%s", key, (time.perf_counter() - started) * 1000,
             "" if complete else " (incomplete; not cached)")
    return result


def _coalesced_build(key: tuple[float, float], lat: float, lon: float,
                     deadline: float) -> tuple[dict[str, Any], bool]:
    """Run one bounded provider pipeline per rounded coordinate.

    Followers wait only for their own remaining request budget; a failed or
    partial build is never retained as a successful memory-cache entry.
    """
    leader = False
    with _inflight_lock:
        future = _inflight.get(key)
        if future is None:
            future = Future()
            _inflight[key] = future
            leader = True
    if not leader:
        try:
            return future.result(timeout=max(0.0, deadline - time.perf_counter()))
        except Exception:
            # The leader will either return a safe partial result or remove its
            # entry.  Never reveal an implementation exception to the caller.
            return _deadline_response(lat, lon, "Recommendation deadline expired while waiting for shared data"), False
    try:
        outcome = (_build_with_deadline(lat, lon, deadline=deadline) if config.DEMO_MODE
                   else _build_recommendation_bounded(lat, lon, deadline))
        future.set_result(outcome)
        return outcome
    except Exception as error:
        future.set_exception(error)
        raise
    finally:
        with _inflight_lock:
            _inflight.pop(key, None)


def _remember(key: tuple[float, float], result: dict[str, Any]) -> None:
    with _response_cache_lock:
        _response_cache[key] = (time.monotonic(), copy.deepcopy(result))
        _response_cache.move_to_end(key)
        while len(_response_cache) > RESPONSE_CACHE_SIZE:
            _response_cache.popitem(last=False)


def _build_with_deadline(lat: float, lon: float, acres: float | None = None,
                         deadline: float | None = None) -> tuple[dict[str, Any], bool]:
    """Use saved data nearby; otherwise return bounded live/partial data."""
    fallback = _demo_fallback(lat, lon, "DEMO_MODE uses the saved demo response")
    if fallback is not None:
        fallback = _apply_acres(fallback, acres)
        fallback["confidence"] = _confidence(fallback, "demo")
        return fallback, False
    return _build_recommendation_bounded(
        lat, lon, deadline if deadline is not None else time.perf_counter() + config.RECOMMENDATION_DEADLINE_S
    )


def _call_with_deadline(fetch: Callable[..., T], deadline: float) -> T:
    """Pass an absolute deadline to modern providers and preserve test fakes."""
    try:
        parameters = inspect.signature(fetch).parameters.values()
        supports_deadline = any(p.name == "deadline" or p.kind == p.VAR_KEYWORD for p in parameters)
    except (TypeError, ValueError):
        supports_deadline = False
    return fetch(deadline=deadline) if supports_deadline else fetch()


def _provider_call(fetch: Callable[..., T], *args: Any, deadline: float) -> T:
    """Call a provider with a deadline when its public signature supports it."""
    try:
        parameters = inspect.signature(fetch).parameters.values()
        supports_deadline = any(p.name == "deadline" or p.kind == p.VAR_KEYWORD for p in parameters)
    except (TypeError, ValueError):
        supports_deadline = False
    return fetch(*args, deadline=deadline) if supports_deadline else fetch(*args)


def _bounded_fetches(fetches: dict[str, Callable[..., Any]], deadline: float,
                    warnings: list[str], failed: list[str]) -> dict[str, Any | None]:
    """Fetch providers on a fixed global worker pool until one absolute deadline."""
    futures: dict[str, Future[Any]] = {
        name: _provider_pool.submit(_attempt, lambda f=fetch: _call_with_deadline(f, deadline), name, warnings, failed)
    """Fetch providers within one request budget using the fixed worker pool.

    A timeout returns a partial response immediately. Work that has not begun
    is cancelled; already-running provider calls are bounded by their own HTTP
    timeout and share this fixed-size pool, so timeout traffic cannot create an
    unbounded number of threads or detached executors.
    """
    futures: dict[str, Future[Any]] = {
        name: _provider_pool.submit(_attempt, fetch, name, warnings, failed)
        for name, fetch in fetches.items()
    }
    done, pending = wait(futures.values(), timeout=max(0.0, deadline - time.perf_counter()))
    for name, future in futures.items():
        if future in pending:
            future.cancel()
            failed.append(name)
            warnings.append(f"{name} timed out; related values are null")
    results = {name: (future.result() if future in done else None)
               for name, future in futures.items()}
    for future in pending:
        future.cancel()
    return results


def _build_recommendation_bounded(lat: float, lon: float, deadline: float,
                                  acres: float | None = None) -> tuple[dict[str, Any], bool]:
    """Build a valid live response within the one recommendation deadline."""
    warnings: list[str] = []
    failed: list[str] = []
    station = fawn.nearest_station(lat, lon)
    source_names = {
        "County lookup (FCC)": lambda: _provider_call(lookup_county, lat, lon, deadline=deadline),
        "Soil data (USDA SSURGO)": lambda: _provider_call(get_soil, lat, lon, deadline=deadline),
        "Weather data (NASA POWER)": lambda: _provider_call(get_daily_weather, lat, lon, deadline=deadline),
    }
    if station:
        source_names["Freeze records (FAWN station)"] = lambda: _provider_call(
            fawn.daily_min_c, station[0]["id"], deadline=deadline)
    results = _bounded_fetches(source_names, deadline, warnings, failed)
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

    market = None
    if county is not None and time.perf_counter() < deadline:
        market_result = _bounded_fetches(
            {"Yield and price data (USDA NASS)": lambda: _provider_call(
                load_market, county["county_fips"], deadline=deadline)},
            deadline, warnings, failed)
        market = market_result["Yield and price data (USDA NASS)"]
    elif county is not None:
        failed.append("Yield and price data (USDA NASS)")
        warnings.append("Yield and price data (USDA NASS) timed out; related values are null")
    climate = _attempt(lambda: summarize(weather), "Climate summary", warnings, failed) if weather is not None else None
    conditions = {field: (soil or {}).get(field) for field in SOIL_FIELDS}
    conditions.update({field: (climate or {}).get(field) for field in CLIMATE_FIELDS})
    crops = rank_crops([score_crop(crop, soil, weather, market, acres) for crop in load_crops().values()])
    response = {
        "location": {"lat": lat, "lon": lon,
                     "county": county["county"] if county else None,
                     "county_fips": county["county_fips"] if county else None,
                     "state": "FL"},
        "conditions": conditions, "crops": crops, "warnings": warnings,
        "scoring": scoring_rules(), "provenance": _provenance("live", failed=failed, station=station),
        "confidence": _confidence({"crops": crops, "warnings": warnings}),
    }
    return response, not failed


def _deadline_response(lat: float, lon: float, warning: str) -> dict[str, Any]:
    """A schema-shaped partial result for a follower whose shared work expired."""
    crops = rank_crops([score_crop(crop, None, None, None) for crop in load_crops().values()])
    response = {"location": {"lat": lat, "lon": lon, "county": None, "county_fips": None, "state": "FL"},
                "conditions": {field: None for field in SOIL_FIELDS + CLIMATE_FIELDS},
                "crops": crops, "warnings": [warning], "scoring": scoring_rules(),
                "provenance": _provenance("live", failed=["deadline"])}
    response["confidence"] = _confidence(response)
    return response


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


def _provenance(mode: str, detail: str | None = None, failed: list[str] | None = None,
                station: tuple[fawn.Station, float] | None = None, cache_status: str | None = None) -> dict[str, Any]:
    failed = failed or []
    metadata = {
        "USDA SSURGO": ("https://sdmdataaccess.sc.egov.usda.gov/", "Current soil survey", "Point/map unit",
                         ["Soil properties depend on survey coverage and reported horizons."]),
        "NASA POWER": ("https://power.larc.nasa.gov/", "2016-01-01 to 2025-12-31", "Nearest POWER grid cell",
                        ["Daily gridded values are not a field-level measurement."]),
        "USDA NASS": ("https://quickstats.nass.usda.gov/", "2012-present; recent five years used for averages", "Florida state and county",
                       ["Some county values are withheld or not reported."]),
        "UF/IFAS FAWN": ("https://fawn.ifas.ufl.edu/", "2016-01-01 to 2025-12-31", "Nearest station within 40 km",
                          ["A nearby station may not represent the exact field."]),
    }
    source_names = tuple(metadata)
    failure_terms = {
        "USDA SSURGO": "SSURGO",
        "NASA POWER": "POWER",
        "USDA NASS": "NASS",
        "UF/IFAS FAWN": "FAWN",
    }
    sources = [
        {"name": name,
         "status": "saved" if mode == "demo" else
                   ("failed" if any(failure_terms[name] in failure for failure in failed) else "live"),
         "detail": detail,
         "url": metadata[name][0], "data_period": metadata[name][1],
         "data_status": ("demo" if mode == "demo" else (cache_status or "live")),
         "geographic_level": metadata[name][2], "limitations": metadata[name][3]}
        for name in source_names
    ]
    return {"mode": mode, "sources": sources,
            "fawn_station": ({"name": station[0]["name"], "distance_km": round(station[1], 1)}
                              if station is not None else None)}


def _confidence(response: dict[str, Any], data_status: str | None = None) -> dict[str, Any]:
    factor_names = ("soil_ph", "drainage", "season_temp", "frost_risk", "rainfall", "local_history")
    crops = response.get("crops", [])
    factors = [factor for crop in crops for factor in crop.get("factors", {}).values()]
    available = round(sum(value is not None for value in factors) / max(len(factors), 1) * FACTOR_COUNT)
    level = "high" if available >= 5 else "medium" if available >= 3 else "low"
    available_names = [name for name in factor_names
                       if any(crop.get("factors", {}).get(name) is not None for crop in crops)]
    missing_names = [name for name in factor_names if name not in available_names]
    history_values = [crop.get("factor_details", {}).get("local_history", {}).get("value") for crop in crops]
    history_text = " ".join(str(value).lower() for value in history_values if value is not None)
    if "withheld" in history_text:
        county_history = "withheld"
    elif history_values and any(value is not None for value in history_values):
        county_history = "available"
    else:
        county_history = "absent"
    status = data_status or (response.get("provenance") or {}).get("mode", "live")
    partial = bool(response.get("warnings")) or bool(missing_names)
    notes = [f"Available factors: {', '.join(available_names) or 'none'}.",
             f"Missing factors: {', '.join(missing_names) or 'none'}.",
             f"Data is {status}.",
             f"County history is {county_history}."]
    if response.get("warnings"):
        notes.append("Result is partial because one or more data sources reported a warning.")
    elif partial:
        notes.append("Result is partial because one or more factors are missing.")
    else:
        notes.append("Result is complete.")
    return {"level": level, "available_factors": available, "total_factors": FACTOR_COUNT,
            "available_factor_names": available_names, "missing_factor_names": missing_names,
            "data_status": status, "county_history_status": county_history,
            "partial": partial, "notes": notes}


@lru_cache(maxsize=None)
def _demo_response(farm: str) -> dict[str, Any]:
    return json.loads((config.DATA_DIR / "demo" / f"{farm}.json").read_text())["recommend"]


def _with_location(result: dict[str, Any], lat: float, lon: float) -> dict[str, Any]:
    """A cached answer echoes this request's coordinates, not the first one's."""
    result["location"]["lat"], result["location"]["lon"] = lat, lon
    return result


def _build_recommendation(lat: float, lon: float, acres: float | None = None) -> tuple[dict[str, Any], bool]:
    """Compatibility entry point using the same bounded live pipeline."""
    return _build_recommendation_bounded(
        lat, lon, time.perf_counter() + config.RECOMMENDATION_DEADLINE_S, acres
    )


def crop_detail(crop_id: str, lat: float, lon: float, acres: float | None = None) -> dict[str, Any] | None:
    """/api/crops/{crop_id} response, or None for an unknown crop id."""
    crop = load_crops().get(crop_id)
    if crop is None:
        return None
    result = recommend(lat, lon, acres)
    scored = next(item for item in result["crops"] if item["id"] == crop_id)
    ph = result["conditions"].get("soil_ph")
    lime_note = (f"pH {ph:g} is below {crop.ph_ideal_min:g}-{crop.ph_ideal_max:g}: a soil test will say how much lime is needed"
                 if ph is not None and ph < crop.ph_ideal_min else None)
    nutrient_plan = {
        "n_lb_per_acre": crop.n_lb_per_acre,
        "soil_test_first": True,
        "lime_note": lime_note,
        "practices": [
            "Soil test before fertilizing",
            "Split nitrogen into several smaller applications",
            "Consider controlled-release fertilizer or fertigation through drip lines",
            "Use cover crops and compost to build organic matter on sandy soils",
            "Follow Florida agricultural Best Management Practices (FDACS)",
        ],
        "sources": [crop.nutrient_source.model_dump(),
                    {"title": "UF/IFAS: What is 4R nutrient stewardship?", "url": "https://edis.ifas.ufl.edu/hs1264"},
                    {"title": "FDACS Agricultural Best Management Practices", "url": "https://www.fdacs.gov/Water/Agricultural-Water-Field-Services/Agricultural-Best-Management-Practices"}],
    }
    action_plan = _action_plan(crop, result["conditions"], scored)
    water_plan = _water_plan(crop, scored)
    management_guidance = _management_guidance(crop)
    return {
        **scored,
        "action_plan": action_plan,
        "requirements": crop.requirements(),
        "general_guidance": crop.general_guidance,
        "extension_links": [link.model_dump() for link in crop.extension_links],
        "nutrient_plan": nutrient_plan,
        "water_plan": water_plan,
        "management_guidance": management_guidance,
        "conditions": result["conditions"],
        "location": result["location"],
        "scoring": result["scoring"],
        "provenance": result.get("provenance"),
    }


def _apply_acres(response: dict[str, Any], acres: float | None) -> dict[str, Any]:
    crops = load_crops()
    for crop_result in response.get("crops", []):
        crop = crops.get(crop_result["id"])
        if crop is None:
            continue
        scale = scale_info(crop, acres)
        crop_result["scale"] = scale
        crop_result["est_gross_value"] = estimated_gross_value(crop_result.get("avg_yield"),
                                                                 crop_result.get("price"), acres)
        note = scale["note"]
        crop_result["score"] = scale_adjusted_score(crop_result["score"], crop, acres)
        if note and note not in crop_result["flags"]:
            crop_result["flags"] = [note, *crop_result["flags"]][:4]
    response["crops"] = rank_crops(response.get("crops", []))
    for crop in response["crops"]:
        crop.setdefault("scale", {"fit": None, "min_practical_acres": 0, "note": None})
        crop.setdefault("est_gross_value", None)
        crop["action_plan"] = _action_plan(crops[crop["id"]], response.get("conditions", {}), crop)
        crop["risk_notes"] = climate_risk_notes(crop.get("flags", []))
    return response


def _action_plan(crop: Any, conditions: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Build plain-language next steps only from committed crop facts and conditions."""
    drainage = conditions.get("drainage")
    before = crop.scale_note
    if drainage:
        before = f"Confirm the field has {drainage.lower()} drainage for this crop; {before.lower()}"
    elif not before:
        before = f"Review the crop's {crop.ph_ideal_min:g}-{crop.ph_ideal_max:g} pH target before planting."
    ph = conditions.get("soil_ph")
    first_test = "Soil test for pH and nutrients before fertilizing"
    if ph is None:
        first_test += "; include pH so lime needs are known"
    else:
        first_test += f"; current reported pH is {ph:g}"
    flags = result.get("flags") or []
    risk = flags[0] if flags else f"Monitor soil pH against the {crop.ph_ideal_min:g}-{crop.ph_ideal_max:g} ideal range."
    link = crop.extension_links[0]
    return {
        "check_before_planting": before,
        "first_test": first_test,
        "planting_window": f"Use the {result.get('season_label', 'Florida growing')} window: plant at the recommended time.",
        "major_risk": risk,
        "uf_ifas_follow_up": {"title": link.title, "url": link.url},
    }


def _water_plan(crop: Any, result: dict[str, Any]) -> dict[str, Any]:
    """Describe water pressure using only existing rainfall thresholds and flags."""
    risks = result.get("risk_notes") or climate_risk_notes(result.get("flags", []))
    dry = next((note for note in risks if note.startswith("Dry-season irrigation pressure:")), None)
    wet = next((note for note in risks if note.startswith("Excessive rainfall:")), None)
    rainfall = (result.get("factors") or {}).get("rainfall")
    if dry:
        status = "below crop threshold"
        sensitivity = "irrigation pressure"
        note = dry.split(": ", 1)[-1]
    elif wet:
        status = "above crop threshold"
        sensitivity = "drainage pressure"
        note = wet.split(": ", 1)[-1]
    elif rainfall is None:
        status = "unknown"
        sensitivity = "unknown until climate data is available"
        note = "Climate data is missing; check soil moisture and irrigation capacity before planting."
    else:
        status = "within crop threshold"
        sensitivity = "routine monitoring"
        note = "Selected-window rainfall is within the crop's committed threshold; monitor field soil moisture."
    low, high = crop.rain_mm_per_month
    link = crop.extension_links[0]
    return {
        "ideal_monthly_low_mm": low,
        "ideal_monthly_high_mm": high,
        "season_status": status,
        "irrigation_sensitivity": sensitivity,
        "note": note,
        "source": {"title": link.title, "url": link.url},
    }


def _management_guidance(crop: Any) -> dict[str, Any]:
    """Return beginner soil-health and rotation steps anchored to committed crop guidance."""
    rotation = next((f"{sentence.strip()}." for sentence in crop.general_guidance.split(".")
                     if "rotat" in sentence.lower()), None)
    if rotation is None:
        rotation = (f"Rotate {crop.name} with a crop from a different botanical family; "
                    "confirm the sequence with UF/IFAS Extension.")
    link = crop.extension_links[0]
    return {
        "soil_health_practices": [
            "Test soil pH and nutrients before fertilizing",
            "Use cover crops and compost to build organic matter on sandy soils",
            "Split nutrient applications to reduce leaching",
            "Keep living roots or residue on the soil between cash crops where practical",
        ],
        "rotation_guidance": rotation,
        "source": {"title": link.title, "url": link.url},
    }
