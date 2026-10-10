"""The demo JSON samples in data/demo must stay valid against the API contract."""

import json

import pytest

from app.config import DATA_DIR, DEMO_FARMS
from app.crops import load_crops
from app.schemas import CropDetail, RecommendResponse


@pytest.mark.parametrize("farm", DEMO_FARMS)
def test_demo_sample_matches_contract(farm: str) -> None:
    sample = json.loads((DATA_DIR / "demo" / f"{farm}.json").read_text())
    assert set(sample) == {"recommend", "crops"}
    recommend = RecommendResponse.model_validate(sample["recommend"])
    assert (recommend.location.lat, recommend.location.lon) == DEMO_FARMS[farm]
    assert set(sample["crops"]) == set(load_crops()) == {crop.id for crop in recommend.crops}
    for crop_id, detail in sample["crops"].items():
        assert CropDetail.model_validate(detail).id == crop_id
