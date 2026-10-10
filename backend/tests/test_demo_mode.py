"""DEMO_MODE serves deterministic saved responses for the public demo."""

import json
import time
from typing import Any

import pytest
from app import cache, config, service
from app.clients import fawn, fcc
from app.market import Market
from app.schemas import Provenance
from app.schemas import RecommendResponse
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
    service.clear_response_cache()
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


def test_far_location_gets_live_response_in_demo_mode(demo: pytest.MonkeyPatch) -> None:
    body = service.recommend(**ORLANDO)
    assert len(body["crops"]) == 13
    assert body["provenance"]["mode"] == "live"
    assert body["location"]["lat"] == ORLANDO["lat"]


def test_failed_source_near_demo_farm_falls_back(demo: pytest.MonkeyPatch) -> None:
    body = service.recommend(**NEAR_HASTINGS)
    assert body["warnings"][0].startswith("Showing cached data for Hastings")


def test_failed_source_far_from_demo_returns_partial_response(demo: pytest.MonkeyPatch) -> None:
    demo.setattr(service, "get_soil", lambda *_: (_ for _ in ()).throw(TimeoutError("soil down")))
    body = service.recommend(**ORLANDO)
    assert len(body["crops"]) == 13
    assert body["conditions"]["soil_ph"] is None
    assert any("SSURGO" in warning for warning in body["warnings"])


def test_slow_source_far_from_demo_returns_before_deadline(demo: pytest.MonkeyPatch) -> None:
    calls = 0

    def slow_weather(*_: float) -> Any:
        nonlocal calls
        calls += 1
        time.sleep(1)
        return fake_weather(0, 0)

    demo.setattr(service, "get_daily_weather", slow_weather)
    started = time.perf_counter()
    body = service.recommend(**ORLANDO)
    assert time.perf_counter() - started < DEADLINE_S + 0.4
    assert len(body["crops"]) == 13
    assert body["conditions"]["annual_precip_mm"] is None
    assert any("NASA POWER" in warning for warning in body["warnings"])
    assert calls == 1


def test_incomplete_far_response_is_retried_not_cached(demo: pytest.MonkeyPatch) -> None:
    calls = 0

    def broken_soil(*_: float) -> Any:
        nonlocal calls
        calls += 1
        raise TimeoutError("soil down")

    demo.setattr(service, "get_soil", broken_soil)
    service.recommend(**ORLANDO)
    service.recommend(**ORLANDO)
    assert calls == 2


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
    body = service.recommend(30.9, -84.0)
    assert len(body["crops"]) == 13


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
def test_exact_demo_coordinates_are_instant_contract_valid_and_offline(
    monkeypatch: pytest.MonkeyPatch, farm: str
) -> None:
    monkeypatch.setattr(config, "DEMO_MODE", True)
    calls: list[str] = []

    def unexpected(name: str) -> Any:
        def fail(*args: Any, **kwargs: Any) -> None:
            calls.append(name)
            raise AssertionError(f"exact demo coordinates called {name}")
        return fail

    for name in ("lookup_county", "get_soil", "get_daily_weather", "load_market"):
        monkeypatch.setattr(service, name, unexpected(name))
    monkeypatch.setattr(fawn, "nearest_station", unexpected("FAWN station lookup"))
    monkeypatch.setattr(fawn, "daily_min_c", unexpected("FAWN daily data"))
    lat, lon = config.DEMO_FARMS[farm]
    started = time.perf_counter()
    body = service.recommend(lat, lon)
    elapsed = time.perf_counter() - started
    RecommendResponse.model_validate(body)
    assert elapsed < 0.5
    assert len(body["crops"]) == 13
    assert body["provenance"]["mode"] == "demo"
    assert body["confidence"]["total_factors"] == 6
    assert calls == []


def test_arbitrary_florida_coordinates_keep_live_behavior(demo: pytest.MonkeyPatch) -> None:
    demo.setattr(config, "DEMO_MODE", False)
    body = service.recommend(**ORLANDO)
    RecommendResponse.model_validate(body)
    assert body["provenance"]["mode"] == "live"
    assert body["location"]["lat"] == ORLANDO["lat"]
    assert len(body["crops"]) == 13


def test_live_provenance_includes_fawn_station() -> None:
    station = {"id": "TEST", "name": "Test Station", "lat": 28.0, "lon": -82.0, "years": 10.0}
    provenance = service._provenance("live", station=(station, 12.345))
    validated = Provenance.model_validate(provenance)
    assert validated.fawn_station is not None
    assert validated.fawn_station.name == "Test Station"
    assert validated.fawn_station.distance_km == 12.3
