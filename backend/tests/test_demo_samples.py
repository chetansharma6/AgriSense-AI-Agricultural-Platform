"""The demo JSON samples in data/demo must stay valid against the API contract."""

import json
import math
from urllib.parse import urlparse

import pytest

from app.config import DATA_DIR, DEMO_FARMS
from app.crops import load_crops
from app.schemas import CropDetail, RecommendResponse


def _assert_finite(value: object, path: str = "response") -> None:
    if isinstance(value, float):
        assert math.isfinite(value), f"non-finite value at {path}"
    elif isinstance(value, dict):
        for key, child in value.items():
            _assert_finite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_finite(child, f"{path}[{index}]")


@pytest.mark.parametrize("farm", DEMO_FARMS)
def test_demo_sample_matches_contract(farm: str) -> None:
    sample = json.loads((DATA_DIR / "demo" / f"{farm}.json").read_text())
    assert set(sample) == {"recommend", "crops"}
    recommend = RecommendResponse.model_validate(sample["recommend"])
    assert (recommend.location.lat, recommend.location.lon) == DEMO_FARMS[farm]
    assert set(sample["crops"]) == set(load_crops()) == {crop.id for crop in recommend.crops}
    for crop_id, detail in sample["crops"].items():
        validated = CropDetail.model_validate(detail)
        assert validated.id == crop_id
        for link in validated.extension_links:
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
    assert len(crops) == 13
    assert len({crop["id"] for crop in crops}) == len(crops)
    assert all(isinstance(crop["score"], int) and 0 <= crop["score"] <= 100 for crop in crops)
    assert scores == sorted(scores, reverse=True)
