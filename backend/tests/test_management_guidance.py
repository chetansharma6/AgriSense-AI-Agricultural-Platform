from app import config, service
from app.crops import get_crop
from app.schemas import CropDetail, ManagementGuidance, WaterPlan


def test_water_plan_uses_existing_dry_rainfall_flag() -> None:
    crop = get_crop("tomato")
    assert crop is not None
    result = {
        "factors": {"rainfall": 72},
        "flags": ["Likely needs irrigation (250 mm rain expected, 270 mm needed)"],
    }
    plan = WaterPlan.model_validate(service._water_plan(crop, result))
    assert plan.season_status == "below crop threshold"
    assert plan.irrigation_sensitivity == "irrigation pressure"
    assert (plan.ideal_monthly_low_mm, plan.ideal_monthly_high_mm) == crop.rain_mm_per_month


def test_water_plan_covers_excess_normal_and_missing_data() -> None:
    crop = get_crop("watermelon")
    assert crop is not None
    excessive = service._water_plan(crop, {
        "factors": {"rainfall": 80},
        "flags": ["Season rainfall 700 mm is above the ideal 430-620 mm: watch for disease and leaching"],
    })
    normal = service._water_plan(crop, {"factors": {"rainfall": 100}, "flags": []})
    missing = service._water_plan(crop, {"factors": {"rainfall": None}, "flags": []})
    assert excessive["season_status"] == "above crop threshold"
    assert normal["season_status"] == "within crop threshold"
    assert missing["season_status"] == "unknown"


def test_management_guidance_uses_committed_rotation_and_safe_source() -> None:
    crop = get_crop("field_corn")
    assert crop is not None
    guidance = ManagementGuidance.model_validate(service._management_guidance(crop))
    assert "Rotating with peanuts, cotton or soybeans" in guidance.rotation_guidance
    assert len(guidance.soil_health_practices) == 4
    assert guidance.source.url.startswith("https://edis.ifas.ufl.edu/")


def test_demo_crop_detail_contract_includes_management_metadata(monkeypatch) -> None:
    monkeypatch.setattr(config, "DEMO_MODE", True)
    detail = service.crop_detail("watermelon", *config.DEMO_FARMS["marianna"])
    assert detail is not None
    validated = CropDetail.model_validate(detail)
    assert validated.water_plan.source.url.startswith("https://")
    assert validated.management_guidance.rotation_guidance
