"""DEMO_MODE: a deadline on live data, with the nearest demo farm's saved response as fallback."""

import json
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import cache, config, service
from app.clients import fcc
from app.main import app
from app.market import Market
from app.utils import haversine_km
from tests.test_api import COUNTY, SOIL, fake_weather

client = TestClient(app)
DEADLINE_S = 0.3  # stands in for the 6 s production deadline
SLOW_S = 1.5  # stands in for a source that hangs
NEAR_HASTINGS = {"lat": 29.75, "lon": -81.45}  # about 6 km from the Hastings demo farm
ORLANDO = {"lat": 28.54, "lon": -81.38}  # in Florida, over 25 km from every demo farm


def saved_demo(farm: str) -> dict[str, Any]:
    return json.loads((config.DATA_DIR / "demo" / f"{farm}.json").read_text())["recommend"]


@pytest.fixture
def demo(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """DEMO_MODE on with a short deadline and fast fake sources; tests make one slow."""
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_DEADLINE_S", DEADLINE_S)
    monkeypatch.setattr(service, "lookup_county", lambda lat, lon: COUNTY)
    monkeypatch.setattr(service, "get_soil", lambda lat, lon: SOIL)
    monkeypatch.setattr(service, "get_daily_weather", fake_weather)
    monkeypatch.setattr(service, "load_market", lambda fips: Market([], [], []))
    return monkeypatch


def slow_soil(lat: float, lon: float) -> dict[str, Any]:
    time.sleep(SLOW_S)
    return SOIL


def test_haversine() -> None:
    assert haversine_km(29.71, -81.50, 29.71, -81.50) == 0
    assert haversine_km(0, 0, 0, 1) == pytest.approx(111.19, abs=0.01)  # one degree of longitude at the equator
    assert haversine_km(29.75, -81.45, *config.DEMO_FARMS["hastings"]) == pytest.approx(6.56, abs=0.01)


def test_slow_source_falls_back_to_nearest_demo_farm(demo: pytest.MonkeyPatch) -> None:
    demo.setattr(service, "get_soil", slow_soil)
    started = time.perf_counter()
    response = client.get("/api/recommend", params=NEAR_HASTINGS)
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert elapsed < DEADLINE_S + 0.5 < SLOW_S  # answered at the deadline, not after the slow source
    body = response.json()
    assert body["warnings"][0] == f"Showing cached data for Hastings (live data took longer than {DEADLINE_S:g} s)"
    saved = saved_demo("hastings")
    assert body["crops"] == saved["crops"]
    assert body["location"] == saved["location"]  # the farm the data is really for


def test_slow_source_far_from_demo_farms_is_quick_503(demo: pytest.MonkeyPatch) -> None:
    demo.setattr(service, "get_soil", slow_soil)
    started = time.perf_counter()
    response = client.get("/api/recommend", params=ORLANDO)
    assert time.perf_counter() - started < DEADLINE_S + 0.5
    assert response.status_code == 503
    assert response.json() == {"detail": "Data sources are slow right now. Try again in a moment, or pick a demo farm."}


def test_failed_source_near_demo_farm_falls_back(demo: pytest.MonkeyPatch) -> None:
    def broken(lat: float, lon: float) -> None:
        raise TimeoutError

    demo.setattr(service, "get_soil", broken)
    body = client.get("/api/recommend", params=NEAR_HASTINGS).json()
    assert body["warnings"][0] == "Showing cached data for Hastings (a live data source failed)"


def test_failed_source_far_from_demo_farms_keeps_live_answer(demo: pytest.MonkeyPatch) -> None:
    def broken(lat: float, lon: float) -> None:
        raise TimeoutError

    demo.setattr(service, "get_soil", broken)
    body = client.get("/api/recommend", params=ORLANDO).json()
    assert body["conditions"]["soil_ph"] is None
    assert any("SSURGO" in warning for warning in body["warnings"])
    assert not any(warning.startswith("Showing cached data") for warning in body["warnings"])


def test_fast_complete_live_answer_is_used(demo: pytest.MonkeyPatch) -> None:
    body = client.get("/api/recommend", params=NEAR_HASTINGS).json()
    assert body["warnings"] == []
    assert body["location"]["lat"] == NEAR_HASTINGS["lat"]


def test_crop_detail_falls_back_too(demo: pytest.MonkeyPatch) -> None:
    demo.setattr(service, "get_soil", slow_soil)
    response = client.get("/api/crops/potato", params=NEAR_HASTINGS)
    assert response.status_code == 200
    body = response.json()
    saved = next(crop for crop in saved_demo("hastings")["crops"] if crop["id"] == "potato")
    assert body["score"] == saved["score"]
    assert body["requirements"]["id"] == "potato"


def test_late_live_result_is_cached_for_next_request(demo: pytest.MonkeyPatch) -> None:
    demo.setattr(service, "get_soil", slow_soil)
    first = client.get("/api/recommend", params=NEAR_HASTINGS).json()
    assert first["warnings"][0].startswith("Showing cached data")
    time.sleep(SLOW_S + 0.3)  # the build finishes in the background
    started = time.perf_counter()
    second = client.get("/api/recommend", params=NEAR_HASTINGS).json()
    assert time.perf_counter() - started < 0.2
    assert second["warnings"] == []
    assert second["location"]["lat"] == NEAR_HASTINGS["lat"]


def test_outside_florida_still_400_in_demo_mode(demo: pytest.MonkeyPatch) -> None:
    demo.setattr(service, "lookup_county", lambda lat, lon: {"county": "Thomas", "county_fips": "13275",
                                                             "state": "GA"})
    response = client.get("/api/recommend", params={"lat": 30.9, "lon": -84.0})
    assert response.status_code == 400


def test_no_deadline_outside_demo_mode(demo: pytest.MonkeyPatch) -> None:
    demo.setattr(config, "DEMO_MODE", False)
    demo.setattr(service, "get_soil", slow_soil)
    body = client.get("/api/recommend", params=NEAR_HASTINGS).json()
    assert body["warnings"] == []  # waited for the slow source instead of falling back


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
    response = client.get("/api/recommend", params={"lat": lat, "lon": lon})
    assert response.status_code == 200
    assert response.json()["provenance"]["mode"] == "demo"
    assert response.json()["confidence"]["total_factors"] == 6
    assert calls == []
