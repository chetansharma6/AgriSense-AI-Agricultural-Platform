"""Deterministic, explainable crop scores.

Each factor is 0-100. The crop score is the weighted mean of the factors
that have data, so a missing source lowers confidence, not the score. If a
critical factor scores below CRITICAL_THRESHOLD, the crop score is capped at
CRITICAL_CAP: a crop the soil or climate rules out cannot rank high on the
strength of its other factors. Climate factors are scored for every Florida
growing window of the crop and the best window is used.
"""

import math
from typing import Any

import pandas as pd

from app.climate import SeasonStats, season_stats
from app.crops import DRAINAGE_CLASSES, Crop, GrowingWindow
from app.market import CountyAcreage, Market, average_yield, county_acreage, price_range

WEIGHTS = {
    "soil_ph": 0.20,
    "drainage": 0.15,
    "season_temp": 0.20,
    "frost_risk": 0.15,
    "rainfall": 0.10,
    "local_history": 0.20,
}
CLIMATE_FACTORS = ("season_temp", "frost_risk", "rainfall")
CRITICAL_FACTORS = ("soil_ph", "drainage", "season_temp", "frost_risk")
CRITICAL_THRESHOLD = 25
CRITICAL_CAP = 45
MAX_FLAGS = 4
FACTOR_NAMES = {
    "soil_ph": "soil pH",
    "drainage": "drainage",
    "season_temp": "season temperature",
    "frost_risk": "freeze risk",
    "rainfall": "rainfall",
    "local_history": "local growing history",
}

DRAINAGE_PENALTY_PER_CLASS = 25
FREEZE_PENALTY_PER_DAY = 10
# A light freeze (-2 to 0 C) counts as half a freeze day, a hard freeze (<= -2 C) as a whole one.
LIGHT_FREEZE_WEIGHT = 0.5
MUCK_SUITABLE_SCORE = 90
# Below CRITICAL_THRESHOLD on purpose: a crop not grown on muck is capped there.
MUCK_UNSUITABLE_SCORE = 15
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


def trapezoid_score(value: float, hard_min: float, ideal_min: float,
                    ideal_max: float, hard_max: float) -> int:
    """100 inside [ideal_min, ideal_max], falling linearly to 0 at the hard limits."""
    if value < ideal_min:
        return max(0, round(100 * (value - hard_min) / (ideal_min - hard_min)))
    if value > ideal_max:
        return max(0, round(100 * (hard_max - value) / (hard_max - ideal_max)))
    return 100


def relative_range_score(value: float, low: float, high: float) -> int:
    """100 inside [low, high], minus 1 point per percent outside the nearer bound."""
    if value < low:
        return max(0, round(100 - 100 * (low - value) / low))
    if value > high:
        return max(0, round(100 - 100 * (value - high) / high))
    return 100


def is_missing(value: float | None) -> bool:
    """None or NaN (NASA POWER and SSURGO gaps arrive as NaN)."""
    return value is None or math.isnan(value)


def score_ph(crop: Crop, ph: float | None) -> Factor:
    low, high = crop.ph_ideal_min, crop.ph_ideal_max
    ideal = f"{low:g}-{high:g}"
    detail = {"value": None if is_missing(ph) else ph, "ideal": ideal, "unit": "pH"}
    if is_missing(ph):
        return None, detail, []
    flags = []
    if ph < low:
        flags.append(f"Soil pH {ph:g} is below the ideal {ideal}: lime may be needed")
    elif ph > high:
        flags.append(f"Soil pH {ph:g} is above the ideal {ideal}: sulfur or acid-forming fertilizer may help")
    return trapezoid_score(ph, crop.ph_min, low, high, crop.ph_max), detail, flags


def score_drainage(crop: Crop, drainage: str | None, texture: str | None) -> Factor:
    driest, wettest = crop.drainage
    ideal = f"{driest} to {wettest.lower()}"
    detail = {"value": drainage, "ideal": ideal}
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
        flags.append(f"{drainage} soil is wetter than ideal ({ideal.lower()}): use raised beds or improve drainage")
    elif index < low:
        flags.append(f"{drainage} soil is drier than ideal ({ideal.lower()}): plan for irrigation and organic matter")
    return range_score(index, low, high, DRAINAGE_PENALTY_PER_CLASS), detail, flags


def score_climate(crop: Crop, stats: SeasonStats | None) -> dict[str, Factor]:
    """Season temperature, frost risk and rainfall for one growing window.
    A missing (NaN) statistic leaves that factor unscored."""
    t_low, t_high = crop.temp_ideal_min_c, crop.temp_ideal_max_c
    # Season rainfall ideal, rounded to 10 mm so it reads cleanly.
    r_low = round(crop.rain_mm_per_month[0] * stats.months, -1) if stats else None
    r_high = round(crop.rain_mm_per_month[1] * stats.months, -1) if stats else None
    temp_detail = {"value": None, "ideal": f"{t_low:g}-{t_high:g}", "unit": "C avg"}
    frost_detail = {"value": None, "ideal": f"<= {crop.max_freeze_days:g}",
                    "unit": "freeze days in season (light freezes count half)"}
    rain_detail = {"value": None, "ideal": f"{r_low:.0f}-{r_high:.0f}" if stats else None, "unit": "mm in season"}
    result: dict[str, Factor] = {"season_temp": (None, temp_detail, []), "frost_risk": (None, frost_detail, []),
                                 "rainfall": (None, rain_detail, [])}
    if stats is None:
        return result

    if not is_missing(stats.mean_temp_c):
        temp = stats.mean_temp_c
        temp_detail["value"] = round(temp, 1)
        temp_flags = []
        if temp > t_high:
            temp_flags.append(f"Season averages {temp:.1f} C, warmer than the ideal {t_low:g}-{t_high:g} C: heat stress risk")
        elif temp < t_low:
            temp_flags.append(f"Season averages {temp:.1f} C, cooler than the ideal {t_low:g}-{t_high:g} C: slower growth")
        result["season_temp"] = (trapezoid_score(temp, crop.temp_min_c, t_low, t_high, crop.temp_max_c),
                                 temp_detail, temp_flags)

    if not is_missing(stats.freeze_days) and not is_missing(stats.hard_freeze_days):
        weighted = weighted_freeze_days(stats)
        frost_detail["value"] = round(weighted, 1)
        excess_freezes = weighted - crop.max_freeze_days
        frost_flags = []
        if excess_freezes > 0:
            frost_flags.append(f"About {stats.freeze_days:.1f} freezing nights in season, {stats.hard_freeze_days:.1f} "
                               f"of them hard (-2 C or colder); crop tolerates about {crop.max_freeze_days:g}: "
                               "plan frost protection or a later planting")
        result["frost_risk"] = (max(0, round(100 - FREEZE_PENALTY_PER_DAY * max(0.0, excess_freezes))),
                                frost_detail, frost_flags)

    if not is_missing(stats.precip_mm):
        rain = stats.precip_mm
        rain_detail["value"] = round(rain)
        rain_flags = []
        if rain < r_low:
            rain_flags.append(f"Likely needs irrigation ({rain:.0f} mm rain expected, {r_low:.0f} mm needed)")
        elif rain > r_high:
            rain_flags.append(f"Season rainfall {rain:.0f} mm is above the ideal {r_low:.0f}-{r_high:.0f} mm: "
                              "watch for disease and leaching")
        result["rainfall"] = (relative_range_score(rain, r_low, r_high), rain_detail, rain_flags)
    return result


def weighted_freeze_days(stats: SeasonStats) -> float:
    """Hard freezes count fully, light ones (above HARD_FREEZE_C) by LIGHT_FREEZE_WEIGHT."""
    light = max(0.0, stats.freeze_days - stats.hard_freeze_days)
    return stats.hard_freeze_days + LIGHT_FREEZE_WEIGHT * light


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
               market: Market | None, acres: float | None = None) -> dict[str, Any]:
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
    score = weighted_score(scores)
    limited_by = [name for name in CRITICAL_FACTORS
                  if scores[name] is not None and scores[name] < CRITICAL_THRESHOLD]
    if limited_by and score is not None:
        score = min(score, CRITICAL_CAP)
    scale = scale_info(crop, acres)
    if scale["fit"] == "too_small" and score is not None:
        score = min(score, 40)
    gross_value = estimated_gross_value(average_yield(market, crop) if market else None,
                                        price_range(market, crop) if market else None, acres)
    flags = ordered_flags(factors, limited_by)
    if scale["note"]:
        flags.insert(0, scale["note"])
    return {
        "id": crop.id,
        "name": crop.name,
        "score": score,
        "season_label": window.label,
        "factors": scores,
        "factor_details": {name: f[1] for name, f in factors.items()},
        "avg_yield": average_yield(market, crop) if market else None,
        "price": price_range(market, crop) if market else None,
        "scale": scale,
        "est_gross_value": gross_value,
        "limited_by": limited_by,
        "flags": flags[:MAX_FLAGS],
    }


def scale_info(crop: Crop, acres: float | None) -> dict[str, Any]:
    if acres is None:
        return {"fit": None, "min_practical_acres": crop.min_practical_acres, "note": None}
    if acres < crop.small_acres:
        return {"fit": "too_small", "min_practical_acres": crop.min_practical_acres,
                "note": f"Usually grown on {crop.min_practical_acres:g}+ acres; hard to make work on {acres:g} acres."}
    if acres < crop.min_practical_acres:
        return {"fit": "small", "min_practical_acres": crop.min_practical_acres,
                "note": f"Small planting of {acres:g} acres; commercial scale is usually {crop.min_practical_acres:g}+ acres."}
    return {"fit": "good", "min_practical_acres": crop.min_practical_acres, "note": None}


def estimated_gross_value(yield_info: dict[str, Any] | None, price: dict[str, Any] | None,
                          acres: float | None) -> dict[str, Any] | None:
    if acres is None or yield_info is None or price is None:
        return None
    yield_unit = yield_info.get("unit", "").upper().replace(" ", "")
    price_unit = price.get("unit", "").upper().replace(" ", "")
    if not yield_unit.endswith("/ACRE") or not price_unit.startswith("$/"):
        return None
    yield_measure = yield_unit.removesuffix("/ACRE")
    price_measure = price_unit.removeprefix("$/")
    if yield_measure != price_measure:
        return None
    return {"low": round(acres * yield_info["value"] * price["low"]),
            "high": round(acres * yield_info["value"] * price["high"]),
            "label": "Rough gross value before costs"}


def ordered_flags(factors: dict[str, Factor], limited_by: list[str]) -> list[str]:
    """Most critical first: "Limited by" flags, then each factor's flags from the
    lowest-scoring factor up (unscored factors last). Deduplicated, at most MAX_FLAGS."""
    flags = [f"Limited by {FACTOR_NAMES[name]}" for name in limited_by]
    by_severity = sorted(factors.items(), key=lambda item: 101 if item[1][0] is None else item[1][0])
    flags += [flag for _, (_, _, factor_flags) in by_severity for flag in factor_flags]
    return list(dict.fromkeys(flags))[:MAX_FLAGS]


def rank_crops(crops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Scored crops by score descending (unscored last), ties by name."""
    return sorted(crops, key=lambda crop: (-(crop["score"] if crop["score"] is not None else -1), crop["name"]))


def scoring_rules() -> dict[str, Any]:
    """The rules the frontend shows next to the factor breakdown."""
    return {
        "weights": dict(WEIGHTS),
        "critical_factors": list(CRITICAL_FACTORS),
        "critical_threshold": CRITICAL_THRESHOLD,
        "critical_cap": CRITICAL_CAP,
    }
