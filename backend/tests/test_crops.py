import json
import copy
import math

import pytest

from app.config import DATA_DIR
from app.crops import Crop, get_crop, load_crops

RAW = json.loads((DATA_DIR / "crops.json").read_text())
REQUIRED_KEYS = {
    "id", "name", "nass_commodity", "nass_class", "nass", "fl_windows",
    "ph_min", "ph_ideal_min", "ph_ideal_max", "ph_max", "drainage", "muck_suitable",
    "temp_min_c", "temp_ideal_min_c", "temp_ideal_max_c", "temp_max_c",
    "max_freeze_days", "rain_mm_per_month", "general_guidance", "extension_links",
    "source_notes", "needs_review", "min_practical_acres", "small_acres", "scale_note",
    "n_lb_per_acre", "nutrient_source", "evidence",
}
EXPECTED_IDS = {
    "peanut", "cotton", "field_corn", "soybean", "sugarcane", "tomato", "watermelon",
    "strawberry", "potato", "sweet_corn", "snap_bean", "bell_pepper", "cabbage",
}
MUCK_CROPS = {"sugarcane", "sweet_corn", "snap_bean", "cabbage"}


def test_exactly_13_unique_crops() -> None:
    ids = [crop["id"] for crop in RAW]
    assert len(ids) == 13
    assert len(set(ids)) == 13
    assert set(ids) == EXPECTED_IDS


@pytest.mark.parametrize("crop", RAW, ids=lambda c: c["id"])
def test_every_required_key_present(crop: dict) -> None:
    assert set(crop) == REQUIRED_KEYS


@pytest.mark.parametrize("crop", RAW, ids=lambda c: c["id"])
def test_ranges_are_ordered(crop: dict) -> None:
    assert crop["ph_min"] <= crop["ph_ideal_min"] <= crop["ph_ideal_max"] <= crop["ph_max"]
    assert crop["temp_min_c"] <= crop["temp_ideal_min_c"] <= crop["temp_ideal_max_c"] <= crop["temp_max_c"]
    low, high = crop["rain_mm_per_month"]
    assert low < high


@pytest.mark.parametrize("crop", RAW, ids=lambda c: c["id"])
def test_windows_have_valid_months(crop: dict) -> None:
    assert crop["fl_windows"]
    for window in crop["fl_windows"]:
        assert 1 <= len(window["months"]) <= 12
        assert all(1 <= month <= 12 for month in window["months"])
        assert int(window["start"][:2]) == window["months"][0]
        assert int(window["end"][:2]) == window["months"][-1]


def test_muck_crops() -> None:
    assert {crop["id"] for crop in RAW if crop["muck_suitable"]} == MUCK_CROPS


def test_links_are_edis() -> None:
    for crop in RAW:
        assert crop["extension_links"]
        assert all(link["url"].startswith("https://edis.ifas.ufl.edu/") for link in crop["extension_links"])


def test_loader() -> None:
    assert len(load_crops()) == 13
    assert get_crop("tomato").name == "Tomato"
    assert get_crop("kale") is None
    assert "general_guidance" not in get_crop("tomato").requirements()
    assert "evidence" not in get_crop("tomato").requirements()


def test_evidence_metadata_is_present_for_every_crop() -> None:
    for crop in RAW:
        evidence = crop["evidence"]
        assert evidence["nutrient_status"] in {"verified", "conditional", "planning_assumption"}
        assert evidence["nitrogen_recommendation_type"] in {"fixed", "range", "conditional", "zero_n"}
        assert evidence["nitrogen_note"]
        assert isinstance(evidence["source_verified"], bool)


@pytest.mark.parametrize("field,value", [
    ("nutrient_source", {"title": "bad", "url": "http://example.test/source"}),
    ("nutrient_source", {"title": "bad", "url": "https://example.test/source"}),
    ("n_lb_per_acre", math.inf),
])
def test_crop_rejects_invalid_nutrient_evidence(field: str, value: object) -> None:
    crop = copy.deepcopy(RAW[0])
    crop[field] = value
    with pytest.raises(ValueError):
        Crop.model_validate(crop)


def test_crop_rejects_absent_evidence_and_incompatible_market_units() -> None:
    missing = copy.deepcopy(RAW[0])
    missing.pop("evidence")
    with pytest.raises(ValueError):
        Crop.model_validate(missing)
    incompatible = copy.deepcopy(RAW[0])
    incompatible["nass"]["price_desc"] = "PEANUTS - PRICE RECEIVED, MEASURED IN $ / CWT"
    with pytest.raises(ValueError, match="incompatible"):
        Crop.model_validate(incompatible)
