"""Crop score cap, flag ordering and ranking."""

from typing import Any

import pandas as pd
import pytest

from app.scoring import (
    CRITICAL_CAP, CRITICAL_FACTORS, WEIGHTS, estimated_gross_value, ordered_flags, rank_crops, score_crop,
    scoring_rules,
)
from tests.test_scoring import make_crop

CROP = make_crop()  # ideal pH 5.5-6.5, drainage well to somewhat poorly drained
GOOD_SOIL = {"soil_ph": 6.0, "drainage": "Well drained", "texture": "sand"}
CONTRACT_KEYS = {"id", "name", "score", "season_label", "factors", "factor_details", "avg_yield", "price",
                 "scale", "est_gross_value", "limited_by", "flags"}


def summer_weather() -> pd.DataFrame:
    """Cold, freezing Jan-Mar; ideal Jun-Aug (20 C, 150 mm a month)."""
    days = pd.date_range("2016-01-01", "2019-12-31", freq="D")
    cold = days.month.isin([1, 2, 3])
    return pd.DataFrame({
        "t_mean_c": [2.0 if c else 20.0 for c in cold],
        "t_min_c": [-5.0 if c else 15.0 for c in cold],
        "precip_mm": 5.0,
    }, index=days)


def test_weights_sum_to_one() -> None:
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)
    assert set(CRITICAL_FACTORS) <= set(WEIGHTS)


def test_critical_factor_caps_score() -> None:
    result = score_crop(CROP, {**GOOD_SOIL, "soil_ph": 4.0}, summer_weather(), None)
    assert result["factors"]["soil_ph"] == 0
    # Uncapped this would be (0.15 + 0.20 + 0.15 + 0.10) * 100 / 0.80 = 75.
    assert result["score"] == CRITICAL_CAP
    assert result["limited_by"] == ["soil_ph"]
    assert result["flags"][0] == "Limited by soil pH"


def test_cap_never_raises_a_low_score() -> None:
    soil = {"soil_ph": 4.0, "drainage": "Very poorly drained", "texture": "sand"}
    narrow = make_crop(drainage=["Excessively drained", "Excessively drained"])
    result = score_crop(narrow, soil, None, None)
    assert result["score"] == 0
    assert result["limited_by"] == ["soil_ph", "drainage"]
    assert result["flags"][:2] == ["Limited by soil pH", "Limited by drainage"]


def test_factor_at_threshold_is_not_critical() -> None:
    # pH 4.75 is a quarter of the way from ph_min 4.5 to ideal 5.5: score 25.
    result = score_crop(CROP, {**GOOD_SOIL, "soil_ph": 4.75}, summer_weather(), None)
    assert result["factors"]["soil_ph"] == 25
    assert result["limited_by"] == []
    assert result["score"] > CRITICAL_CAP


def test_missing_factor_is_not_critical() -> None:
    result = score_crop(CROP, None, summer_weather(), None)
    assert result["factors"]["soil_ph"] is None
    assert result["limited_by"] == []
    assert result["score"] == 100


def test_picks_the_higher_scoring_window() -> None:
    result = score_crop(CROP, GOOD_SOIL, summer_weather(), None)
    assert result["season_label"] == "Summer: plant Jun"
    assert result["score"] == 100


def test_output_matches_contract() -> None:
    result = score_crop(CROP, GOOD_SOIL, summer_weather(), None)
    assert set(result) == CONTRACT_KEYS
    assert set(result["factors"]) == set(WEIGHTS) == set(result["factor_details"])
    assert set(scoring_rules()) == {"weights", "critical_factors", "critical_threshold", "critical_cap"}


def test_scale_gate_caps_too_small_and_flags_small() -> None:
    too_small = score_crop(CROP, GOOD_SOIL, summer_weather(), None, acres=1)
    assert too_small["scale"]["fit"] == "too_small"
    assert too_small["score"] <= 40
    assert too_small["flags"][0].startswith("Usually grown on 10+ acres")
    small = score_crop(CROP, GOOD_SOIL, summer_weather(), None, acres=5)
    assert small["scale"]["fit"] == "small"
    assert small["score"] == 100
    assert "Small planting" in small["flags"][0]


def test_no_acres_preserves_score_and_has_no_scale_note() -> None:
    result = score_crop(CROP, GOOD_SOIL, summer_weather(), None)
    assert result["score"] == 100
    assert result["scale"] == {"fit": None, "min_practical_acres": 10, "note": None}


def test_gross_value_requires_matching_units() -> None:
    yield_info = {"value": 1000, "unit": "LB / ACRE"}
    price = {"low": 0.50, "high": 0.75, "unit": "$ / LB"}
    assert estimated_gross_value(yield_info, price, 2) == {
        "low": 1000, "high": 1500, "label": "Rough gross value before costs"
    }
    assert estimated_gross_value(yield_info, {**price, "unit": "$ / CWT"}, 2) is None


def test_flags_most_critical_first_deduplicated_and_capped() -> None:
    factors: dict[str, Any] = {
        "soil_ph": (60, {}, ["pH flag"]),
        "drainage": (10, {}, ["drainage flag", "pH flag"]),
        "season_temp": (None, {}, ["unscored flag"]),
        "frost_risk": (40, {}, ["frost flag"]),
        "rainfall": (90, {}, ["rain flag"]),
        "local_history": (100, {}, []),
    }
    assert ordered_flags(factors, ["drainage"]) == [
        "Limited by drainage", "drainage flag", "pH flag", "frost flag"]


def crop(name: str, score: int | None) -> dict[str, Any]:
    return {"name": name, "score": score}


def test_rank_sorts_by_score_then_name() -> None:
    ranked = rank_crops([crop("Tomato", 80), crop("Cabbage", 80), crop("Potato", 95), crop("Bean", None),
                         crop("Apple", 10)])
    assert [c["name"] for c in ranked] == ["Potato", "Cabbage", "Tomato", "Apple", "Bean"]


def test_muck_caps_crops_not_grown_on_muck() -> None:
    muck = {"soil_ph": 6.0, "drainage": "Very poorly drained", "texture": "muck"}
    result = score_crop(CROP, muck, summer_weather(), None)
    assert result["factors"]["drainage"] == 15
    assert result["limited_by"] == ["drainage"]
    assert result["score"] == CRITICAL_CAP
    on_muck = score_crop(make_crop(muck_suitable=True), muck, summer_weather(), None)
    assert on_muck["limited_by"] == [] and on_muck["score"] > CRITICAL_CAP
