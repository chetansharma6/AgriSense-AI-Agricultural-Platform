import math

from app import config, service
from app.schemas import RecommendResponse


def test_every_demo_crop_has_contract_valid_action_plan(monkeypatch) -> None:
    monkeypatch.setattr(config, "DEMO_MODE", True)
    for lat, lon in config.DEMO_FARMS.values():
        response = service.recommend(lat, lon)
        validated = RecommendResponse.model_validate(response)
        assert len(validated.crops) == 13
        for crop in validated.crops:
            plan = crop.action_plan
            assert plan.check_before_planting
            assert plan.first_test.startswith("Soil test")
            assert plan.planting_window.startswith("Use the ")
            assert plan.major_risk
            assert plan.uf_ifas_follow_up.url.startswith("https://edis.ifas.ufl.edu/")


def test_action_plan_uses_reported_soil_condition(monkeypatch) -> None:
    monkeypatch.setattr(config, "DEMO_MODE", True)
    response = service.recommend(*config.DEMO_FARMS["hastings"])
    tomato = next(crop for crop in response["crops"] if crop["id"] == "tomato")
    assert "pH" in tomato["action_plan"]["first_test"]
    assert math.isfinite(response["conditions"]["soil_ph"])
