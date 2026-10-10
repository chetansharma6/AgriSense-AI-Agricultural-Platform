"""Deterministic, explainable crop scores.

Each factor is 0-100. The crop score is the weighted mean of the factors
that have data, so a missing source lowers confidence, not the score.
Climate factors are scored for every Florida growing window of the crop and
the best window is used.
"""

import math
from typing import Any

import pandas as pd

from app.climate import SeasonStats, season_stats
from app.crops import DRAINAGE_CLASSES, Crop, GrowingWindow
from app.market import CountyAcreage, Market, average_yield, county_acreage, price_range

WEIGHTS = {
    "soil_ph": 0.15,
    "drainage": 0.15,
    "season_temp": 0.20,
    "frost_risk": 0.15,
    "rainfall": 0.10,
    "local_history": 0.25,
}
CLIMATE_FACTORS = ("season_temp", "frost_risk", "rainfall")

PH_PENALTY_PER_UNIT = 40
DRAINAGE_PENALTY_PER_CLASS = 25
TEMP_PENALTY_PER_C = 10
FREEZE_PENALTY_PER_DAY = 10
MUCK_SUITABLE_SCORE = 90
MUCK_UNSUITABLE_SCORE = 30
# Local history: 60 for any reported acreage, rising to 100 at FULL_HISTORY_ACRES
# on a log scale; 75 when NASS withholds the number; 30 when not grown.
HISTORY_BASE_SCORE = 60
FULL_HISTORY_ACRES = 5000
WITHHELD_SCORE = 75
NOT_IN_COUNTY_SCORE = 30

Factor = tuple[int | None, dict[str, Any], list[str]]  # score, detail, flags


def range_score(value: float, low: float, high: float, penalty_per_unit: float) -> int:
    """100 inside [low, high], minus penalty_per_unit per unit outside, floored at 0."""
    distance = max(low - value, value - high, 0.0)
    return max(0, round(100 - penalty_per_unit * distance))


def relative_range_score(value: float, low: float, high: float) -> int:
    """100 inside [low, high], minus 1 point per percent outside the nearer bound."""
    if value < low:
        return max(0, round(100 - 100 * (low - value) / low))
    if value > high:
        return max(0, round(100 - 100 * (value - high) / high))
    return 100


def score_ph(crop: Crop, ph: float | None) -> Factor:
    low, high = crop.ph
    detail = {"value": ph, "ideal": f"{low:g}-{high:g}", "unit": "pH"}
    if ph is None:
        return None, detail, []
    flags = []
    if ph < low:
        flags.append("Soil is more acidic than ideal: lime may be needed")
    elif ph > high:
        flags.append("Soil pH is above ideal: sulfur or acid-forming fertilizer may help")
    return range_score(ph, low, high, PH_PENALTY_PER_UNIT), detail, flags


def score_drainage(crop: Crop, drainage: str | None, texture: str | None) -> Factor:
    driest, wettest = crop.drainage
    detail = {"value": drainage, "ideal": f"{driest} to {wettest.lower()}"}
    if texture == "muck":
        if crop.muck_suitable:
            return MUCK_SUITABLE_SCORE, detail, ["Muck soil: needs managed drainage and water table control"]
        return MUCK_UNSUITABLE_SCORE, detail, ["Muck soil: not typical for this crop"]
    if drainage not in DRAINAGE_CLASSES:
        return None, detail, []
    index = DRAINAGE_CLASSES.index(drainage)
    low, high = DRAINAGE_CLASSES.index(driest), DRAINAGE_CLASSES.index(wettest)
    flags = []
    if index > high:
        flags.append("Wetter soil than ideal: use raised beds or improve drainage")
    elif index < low:
        flags.append("Droughty soil: plan for irrigation and organic matter")
    return range_score(index, low, high, DRAINAGE_PENALTY_PER_CLASS), detail, flags


def score_climate(crop: Crop, stats: SeasonStats | None) -> dict[str, Factor]:
    """Season temperature, frost risk and rainfall for one growing window."""
    t_low, t_high = crop.season_temp_c
    # Season rainfall ideal, rounded to 10 mm so it reads cleanly.
    r_low = round(crop.rain_mm_per_month[0] * stats.months, -1) if stats else None
    r_high = round(crop.rain_mm_per_month[1] * stats.months, -1) if stats else None
    temp_detail = {"value": None, "ideal": f"{t_low:g}-{t_high:g}", "unit": "C avg"}
    frost_detail = {"value": None, "ideal": f"<= {crop.max_freeze_days:g}", "unit": "freeze days in season"}
    rain_detail = {"value": None, "ideal": f"{r_low:.0f}-{r_high:.0f}" if stats else None, "unit": "mm in season"}
    if stats is None:
        return {"season_temp": (None, temp_detail, []), "frost_risk": (None, frost_detail, []),
                "rainfall": (None, rain_detail, [])}

    temp_detail["value"] = round(stats.mean_temp_c, 1)
    frost_detail["value"] = round(stats.freeze_days, 1)
    rain_detail["value"] = round(stats.precip_mm)

    temp_flags = []
    if stats.mean_temp_c > t_high:
        temp_flags.append("Season is warmer than ideal: heat stress risk")
    elif stats.mean_temp_c < t_low:
        temp_flags.append("Season is cooler than ideal: slower growth")
    frost_flags = []
    excess_freezes = stats.freeze_days - crop.max_freeze_days
    if excess_freezes > 0:
        frost_flags.append("Freeze risk in season: plan frost protection or a later planting")
    rain_flags = []
    if stats.precip_mm < r_low:
        rain_flags.append("May need supplemental irrigation")
    elif stats.precip_mm > r_high:
        rain_flags.append("Season rainfall above ideal: watch for disease and waterlogging")

    return {
        "season_temp": (range_score(stats.mean_temp_c, t_low, t_high, TEMP_PENALTY_PER_C), temp_detail, temp_flags),
        "frost_risk": (max(0, round(100 - FREEZE_PENALTY_PER_DAY * max(0.0, excess_freezes))), frost_detail, frost_flags),
        "rainfall": (relative_range_score(stats.precip_mm, r_low, r_high), rain_detail, rain_flags),
    }


def score_local_history(acreage: CountyAcreage | None) -> Factor:
    detail: dict[str, Any] = {"value": None, "ideal": "Grown locally"}
    if acreage is None:
        return None, detail, []
    if not acreage.grown:
        detail["value"] = "Not reported in county"
        return NOT_IN_COUNTY_SCORE, detail, ["Not reported in this county: confirm local buyers and markets"]
    if acreage.acres is None:
        detail["value"] = f"Grown in county ({acreage.year} Census, acreage withheld)"
        return WITHHELD_SCORE, detail, []
    detail["value"] = f"{acreage.acres:,.0f} acres in county ({acreage.year} Census)"
    share = math.log10(max(acreage.acres, 1)) / math.log10(FULL_HISTORY_ACRES)
    return round(HISTORY_BASE_SCORE + (100 - HISTORY_BASE_SCORE) * min(1.0, share)), detail, []


def weighted_score(factors: dict[str, int | None], names: tuple[str, ...] | None = None) -> int | None:
    """Weighted mean of the non-null factors."""
    names = names or tuple(WEIGHTS)
    present = [(WEIGHTS[n], factors[n]) for n in names if factors.get(n) is not None]
    total = sum(weight for weight, _ in present)
    if not total:
        return None
    return round(sum(weight * value for weight, value in present) / total)


def best_window(crop: Crop, weather: pd.DataFrame | None) -> tuple[GrowingWindow, dict[str, Factor]]:
    """The growing window with the highest climate sub-score."""
    best: tuple[int, GrowingWindow, dict[str, Factor]] | None = None
    for window in crop.fl_windows:
        stats = season_stats(weather, window.start, window.end) if weather is not None else None
        climate = score_climate(crop, stats)
        subscore = weighted_score({name: f[0] for name, f in climate.items()}, CLIMATE_FACTORS) or 0
        if best is None or subscore > best[0]:
            best = (subscore, window, climate)
    assert best is not None, f"{crop.id} has no growing windows"
    return best[1], best[2]


def score_crop(crop: Crop, soil: dict[str, Any] | None, weather: pd.DataFrame | None,
               market: Market | None) -> dict[str, Any]:
    """The API crop object for one crop."""
    soil = soil or {}
    window, climate = best_window(crop, weather)
    factors: dict[str, Factor] = {
        "soil_ph": score_ph(crop, soil.get("soil_ph")),
        "drainage": score_drainage(crop, soil.get("drainage"), soil.get("texture")),
        **climate,
        "local_history": score_local_history(county_acreage(market, crop) if market else None),
    }
    scores = {name: f[0] for name, f in factors.items()}
    return {
        "id": crop.id,
        "name": crop.name,
        "score": weighted_score(scores),
        "season_label": window.label,
        "factors": scores,
        "factor_details": {name: f[1] for name, f in factors.items()},
        "avg_yield": average_yield(market, crop) if market else None,
        "price": price_range(market, crop) if market else None,
        "flags": [flag for f in factors.values() for flag in f[2]],
    }
