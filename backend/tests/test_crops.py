import json

import pytest

from app.config import DATA_DIR
from app.crops import get_crop, load_crops

RAW = json.loads((DATA_DIR / "crops.json").read_text())
REQUIRED_KEYS = {
    "id", "name", "nass_commodity", "nass_class", "nass", "fl_windows",
    "ph_min", "ph_ideal_min", "ph_ideal_max", "ph_max", "drainage", "muck_suitable",
    "temp_min_c", "temp_ideal_min_c", "temp_ideal_max_c", "temp_max_c",
    "max_freeze_days", "rain_mm_per_month", "general_guidance", "extension_links",
    "source_notes", "needs_review", "min_practical_acres", "small_acres", "scale_note",
    "n_lb_per_acre", "nutrient_source",
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
