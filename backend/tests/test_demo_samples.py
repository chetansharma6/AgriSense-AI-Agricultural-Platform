"""The demo JSON samples in data/demo must stay valid against the API contract."""

import json
import math
import copy
from urllib.parse import urlparse

import pytest

from app.config import DATA_DIR, DEMO_FARMS
from app.crops import load_crops
from app.schemas import CropDetail, RecommendResponse
from app import service
from app.schemas import RawDemoFixture


def _assert_finite(value: object, path: str = "response") -> None:
    if isinstance(value, float):
        assert math.isfinite(value), f"non-finite value at {path}"
    elif isinstance(value, dict):
        for key, child in value.items():
            _assert_finite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_finite(child, f"{path}[{index}]")


def _assert_response_invariants(response: dict) -> None:
    crops = response["crops"]
    assert len(crops) == 13
    assert len({crop["id"] for crop in crops}) == len(crops)
    assert all(crop["score"] is None or 0 <= crop["score"] <= 100 for crop in crops)
    assert [(-(crop["score"] if crop["score"] is not None else -1), crop["name"]) for crop in crops] == sorted(
        (-(crop["score"] if crop["score"] is not None else -1), crop["name"]) for crop in crops)
    for crop in crops:
        assert list(crop["factors"]) == ["soil_ph", "drainage", "season_temp", "frost_risk", "rainfall", "local_history"]
        assert all(value is None or isinstance(value, int) and 0 <= value <= 100 for value in crop["factors"].values())
        assert crop["avg_yield"] is None or "/ ACRE" in (crop["avg_yield"]["unit"] or "")
        assert crop["price"] is None or (crop["price"]["unit"] or "").startswith("$ / ")
    provenance = response.get("provenance")
    if provenance is not None:
        assert provenance["mode"] in {"live", "demo"}
        assert all(source["status"] in {"live", "saved", "failed", "no data"}
                   and (source["detail"] is None or isinstance(source["detail"], str))
                   for source in provenance["sources"])
        if provenance["fawn_station"] is not None:
            assert provenance["fawn_station"]["name"]
            assert math.isfinite(provenance["fawn_station"]["distance_km"])


@pytest.mark.parametrize("farm", DEMO_FARMS)
def test_demo_sample_matches_contract(farm: str, monkeypatch: pytest.MonkeyPatch) -> None:
    sample = json.loads((DATA_DIR / "demo" / f"{farm}.json").read_text())
    assert set(sample) == {"recommend", "crops"}
    # Committed recommendation data is a raw source fixture.  The API adds
    # deterministic presentation fields at one boundary before validation.
    response = service._apply_acres(copy.deepcopy(sample["recommend"]), None)
    response["provenance"] = service._provenance("demo", "Saved fixture")
    response["confidence"] = service._confidence(response, "demo")
    recommend = RecommendResponse.model_validate(response)
    assert (recommend.location.lat, recommend.location.lon) == DEMO_FARMS[farm]
    assert set(sample["crops"]) == set(load_crops()) == {crop.id for crop in recommend.crops}
    monkeypatch.setattr(service.config, "DEMO_MODE", True)
    lat, lon = DEMO_FARMS[farm]
    for crop_id in sample["crops"]:
        detail = service.crop_detail(crop_id, lat, lon)
        assert detail is not None
        validated = CropDetail.model_validate(detail)
        assert validated.id == crop_id
        for link in validated.extension_links:
            parsed = urlparse(link.url)
            assert parsed.scheme == "https"
            assert parsed.netloc


@pytest.mark.parametrize("farm", DEMO_FARMS)
def test_raw_demo_fixture_matches_its_source_contract(farm: str) -> None:
    sample = json.loads((DATA_DIR / "demo" / f"{farm}.json").read_text())
    fixture = RawDemoFixture.model_validate(sample)
    recommend = fixture.recommend
    assert (recommend.location.lat, recommend.location.lon) == DEMO_FARMS[farm]
    assert set(fixture.crops) == set(load_crops()) == {crop.id for crop in recommend.crops}
    for crop_id, detail in fixture.crops.items():
        assert detail.id == crop_id
        for link in detail.extension_links:
            parsed = urlparse(link.url)
            assert parsed.scheme == "https"
            assert parsed.netloc


@pytest.mark.parametrize("farm", DEMO_FARMS)
def test_demo_recommendation_integrity(farm: str) -> None:
    sample = json.loads((DATA_DIR / "demo" / f"{farm}.json").read_text())
    response = sample["recommend"]
    crops = response["crops"]
    scores = [crop["score"] for crop in crops]

    _assert_finite(response)
    _assert_response_invariants(response)
    assert all(isinstance(crop["score"], int) and 0 <= crop["score"] <= 100 for crop in crops)
    assert scores == sorted(scores, reverse=True)


@pytest.mark.parametrize("farm", DEMO_FARMS)
def test_demo_detail_links_and_nutrient_sources_are_https(farm: str) -> None:
    sample = json.loads((DATA_DIR / "demo" / f"{farm}.json").read_text())
    for detail in sample["crops"].values():
        links = detail["extension_links"] + detail.get("nutrient_plan", {}).get("sources", [])
        assert all(urlparse(link["url"]).scheme == "https" and urlparse(link["url"]).netloc for link in links)
