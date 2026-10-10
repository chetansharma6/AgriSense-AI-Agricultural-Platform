"""DEMO_MODE serves deterministic saved responses for the public demo."""

import json
from typing import Any

import pytest
from app import cache, config, service
from app.clients import fawn, fcc
from app.market import Market
from app.utils import haversine_km
from tests.test_api import COUNTY, SOIL, fake_weather

DEADLINE_S = 0.3  # stands in for the 6 s production deadline
NEAR_HASTINGS = {"lat": 29.75, "lon": -81.45}  # about 6 km from the Hastings demo farm
ORLANDO = {"lat": 28.54, "lon": -81.38}  # in Florida, over 25 km from every demo farm


def saved_demo(farm: str) -> dict[str, Any]:
    return json.loads((config.DATA_DIR / "demo" / f"{farm}.json").read_text())["recommend"]


@pytest.fixture
def demo(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Enable deterministic demo mode."""
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_DEADLINE_S", DEADLINE_S)
    monkeypatch.setattr(service, "lookup_county", lambda lat, lon: COUNTY)
    monkeypatch.setattr(service, "get_soil", lambda lat, lon: SOIL)
    monkeypatch.setattr(service, "get_daily_weather", fake_weather)
    monkeypatch.setattr(service, "load_market", lambda fips: Market([], [], []))
    monkeypatch.setattr(fawn, "nearest_station", lambda lat, lon: None)
    return monkeypatch


def test_haversine() -> None:
    assert haversine_km(29.71, -81.50, 29.71, -81.50) == 0
    assert haversine_km(0, 0, 0, 1) == pytest.approx(111.19, abs=0.01)  # one degree of longitude at the equator
    assert haversine_km(29.75, -81.45, *config.DEMO_FARMS["hastings"]) == pytest.approx(6.56, abs=0.01)


def test_nearby_location_uses_nearest_saved_demo(demo: pytest.MonkeyPatch) -> None:
    body = service.recommend(**NEAR_HASTINGS)
    assert body["warnings"][0] == "Showing cached data for Hastings (DEMO_MODE uses the saved demo response)"
    saved = saved_demo("hastings")
    assert body["crops"] == saved["crops"]
    assert body["location"] == saved["location"]  # the farm the data is really for


def test_far_location_is_rejected_in_demo_mode(demo: pytest.MonkeyPatch) -> None:
    with pytest.raises(service.SourcesTooSlow):
        service.recommend(**ORLANDO)


def test_failed_source_near_demo_farm_falls_back(demo: pytest.MonkeyPatch) -> None:
    body = service.recommend(**NEAR_HASTINGS)
    assert body["warnings"][0].startswith("Showing cached data for Hastings")


def test_far_location_does_not_call_live_sources(demo: pytest.MonkeyPatch) -> None:
    demo.setattr(service, "get_soil", lambda *_: pytest.fail("live source called"))
    with pytest.raises(service.SourcesTooSlow):
        service.recommend(**ORLANDO)


def test_nearby_location_is_deterministic(demo: pytest.MonkeyPatch) -> None:
    body = service.recommend(**NEAR_HASTINGS)
    assert body["warnings"][0].startswith("Showing cached data")
    assert body["location"] == saved_demo("hastings")["location"]


def test_crop_detail_falls_back_too(demo: pytest.MonkeyPatch) -> None:
    body = service.crop_detail("potato", **NEAR_HASTINGS)
    saved = next(crop for crop in saved_demo("hastings")["crops"] if crop["id"] == "potato")
    assert body["score"] == saved["score"]
    assert body["requirements"]["id"] == "potato"


def test_far_non_demo_location_is_unavailable(demo: pytest.MonkeyPatch) -> None:
    with pytest.raises(service.SourcesTooSlow):
        service.recommend(30.9, -84.0)


def test_no_deadline_outside_demo_mode(demo: pytest.MonkeyPatch) -> None:
    demo.setattr(config, "DEMO_MODE", False)
    body = service.recommend(**NEAR_HASTINGS)
    assert body["provenance"]["mode"] == "live"


def test_demo_mode_still_serves_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    county = {"county": "St. Johns", "county_fips": "12109", "state": "FL"}
    cache.write_cache("fcc", {"lat": 29.71, "lon": -81.5}, county)
    monkeypatch.setattr(config, "DEMO_MODE", True)
    assert fcc.lookup_county(29.71, -81.50) == county


@pytest.mark.parametrize("farm", config.DEMO_FARMS)
def test_exact_demo_coordinates_never_call_live_sources(monkeypatch: pytest.MonkeyPatch, farm: str) -> None:
    monkeypatch.setattr(config, "DEMO_MODE", True)
    calls = []

    def unexpected(*args: Any, **kwargs: Any) -> None:
        calls.append(True)
        raise AssertionError("exact demo coordinates must use saved data")

    monkeypatch.setattr(service, "_build_recommendation", unexpected)
    lat, lon = config.DEMO_FARMS[farm]
    body = service.recommend(lat, lon)
    assert body["provenance"]["mode"] == "demo"
    assert body["confidence"]["total_factors"] == 6
    assert calls == []
