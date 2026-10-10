"""Builds API responses: gathers sources in parallel, then scores every crop.

A failed source never fails the request: its values become null and a
message is added to warnings.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

from app.climate import summarize
from app.clients.fcc import lookup_county
from app.clients.power import get_daily_weather
from app.clients.soil import SoilNotFound, get_soil
from app.crops import load_crops
from app.market import load_market
from app.scoring import score_crop

T = TypeVar("T")

SOIL_FIELDS = ("soil_ph", "organic_matter_pct", "sand_pct", "clay_pct", "texture", "drainage")
CLIMATE_FIELDS = ("annual_precip_mm", "frost_free_days", "last_spring_frost", "first_fall_frost",
                  "avg_summer_high_c", "avg_winter_low_c")


class OutsideFlorida(ValueError):
    """The point is not in Florida."""


def _attempt(fetch: Callable[[], T], source: str, warnings: list[str]) -> T | None:
    try:
        return fetch()
    except SoilNotFound as error:
        warnings.append(f"{error}; soil values are null")
        return None
    except Exception as error:  # any source failure becomes a warning
        warnings.append(f"{source} unavailable ({type(error).__name__}); related values are null")
        return None


def recommend(lat: float, lon: float) -> dict[str, Any]:
    """Full /api/recommend response for a Florida point."""
    warnings: list[str] = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        county_job = pool.submit(_attempt, lambda: lookup_county(lat, lon), "County lookup (FCC)", warnings)
        soil_job = pool.submit(_attempt, lambda: get_soil(lat, lon), "Soil data (USDA SSURGO)", warnings)
        weather_job = pool.submit(_attempt, lambda: get_daily_weather(lat, lon), "Weather data (NASA POWER)", warnings)
        county, soil, weather = county_job.result(), soil_job.result(), weather_job.result()

    if county is not None and county["state"] != "FL":
        raise OutsideFlorida
    if county is None and not any("FCC" in w for w in warnings):
        warnings.append("No county found at this point (offshore or water?); local history is null")
    if soil is not None and soil["soil_ph"] is None:
        warnings.append("Soil survey reports no pH for this soil; the pH factor is skipped")

    market = _attempt(lambda: load_market(county["county_fips"] if county else None),
                      "Yield and price data (USDA NASS)", warnings)

    climate = _attempt(lambda: summarize(weather), "Climate summary", warnings) if weather is not None else None
    conditions = {field: (soil or {}).get(field) for field in SOIL_FIELDS}
    conditions.update({field: (climate or {}).get(field) for field in CLIMATE_FIELDS})

    crops = [score_crop(crop, soil, weather, market) for crop in load_crops().values()]
    crops.sort(key=lambda crop: crop["score"] if crop["score"] is not None else -1, reverse=True)

    return {
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
    }


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
    }
