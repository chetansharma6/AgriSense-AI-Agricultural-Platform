"""Endpoint tests with every data source faked."""

from typing import Any
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import service
from app.clients import fawn
from app.main import app
from app.market import Market
from app.schemas import CropDetail, RecommendResponse

client = TestClient(app)

COUNTY = {"county": "St. Johns", "county_fips": "12109", "state": "FL"}
SOIL = {"soil_ph": 5.6, "organic_matter_pct": 1.8, "sand_pct": 88.0, "clay_pct": 4.0,
        "texture": "sand", "drainage": "Poorly drained", "map_unit": "Test sand"}
FACTORS = {"soil_ph", "drainage", "season_temp", "frost_risk", "rainfall", "local_history"}
CROP_KEYS = {"id", "name", "score", "season_label", "factors", "factor_details", "avg_yield", "price",
             "scale", "est_gross_value", "limited_by", "flags", "action_plan", "risk_notes"}


def fake_weather(lat: float, lon: float) -> pd.DataFrame:
    days = pd.date_range("2020-01-01", "2023-12-31", freq="D")
    seasonal = [15 + 10 * (1 - abs(day.month - 7) / 6) for day in days]
    return pd.DataFrame({"t_mean_c": seasonal, "t_max_c": [t + 6 for t in seasonal],
                         "t_min_c": [t - 6 for t in seasonal], "precip_mm": 3.5,
                         "solar_kwh_m2": 5.0}, index=days)


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    fakes: dict[str, Any] = {"county": COUNTY, "soil": SOIL}
    monkeypatch.setattr(service, "lookup_county", lambda lat, lon: fakes["county"])
    monkeypatch.setattr(service, "get_soil", lambda lat, lon: fakes["soil"])
    monkeypatch.setattr(service, "get_daily_weather", fake_weather)
    monkeypatch.setattr(fawn, "nearest_station", lambda lat, lon: None)
    # Like the real load_market: no county rows when the county is unknown.
    monkeypatch.setattr(service, "load_market", lambda fips: Market(None if fips is None else [], [], []))
    return fakes


def test_recommend_matches_contract(sources: dict[str, Any]) -> None:
    body = client.get("/api/recommend", params={"lat": 29.71, "lon": -81.50}).json()
    assert set(body) == {"location", "conditions", "crops", "warnings", "scoring", "provenance", "confidence"}
    assert set(body["scoring"]) == {"weights", "critical_factors", "critical_threshold", "critical_cap"}
    assert body["location"] == {"lat": 29.71, "lon": -81.5, "county": "St. Johns",
                                "county_fips": "12109", "state": "FL"}
    assert body["conditions"]["texture"] == "sand"
    assert body["conditions"]["frost_free_days"] == 365
    assert len(body["crops"]) == 13
    scores = [crop["score"] for crop in body["crops"]]
    assert scores == sorted(scores, reverse=True)
    for crop in body["crops"]:
        assert set(crop) == CROP_KEYS
        assert set(crop["factors"]) == FACTORS == set(crop["factor_details"])
        # Drainage and local history have no unit; the key must be absent, not null.
        assert set(crop["factor_details"]["drainage"]) == {"value", "ideal"}
        assert set(crop["factor_details"]["local_history"]) == {"value", "ideal"}
        assert crop["factor_details"]["soil_ph"]["unit"] == "pH"
        assert all(0 <= v <= 100 for v in crop["factors"].values() if v is not None)
    assert body["warnings"] == []
    assert body["provenance"]["mode"] == "live"
    assert body["confidence"]["total_factors"] == 6


def test_failed_source_becomes_warning(sources: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(lat: float, lon: float) -> None:
        raise TimeoutError

    monkeypatch.setattr(service, "get_soil", broken)
    body = client.get("/api/recommend", params={"lat": 29.71, "lon": -81.50}).json()
    assert body["conditions"]["soil_ph"] is None
    assert body["crops"][0]["factors"]["soil_ph"] is None
    assert any("SSURGO" in warning for warning in body["warnings"])
    statuses = {source["name"]: source["status"] for source in body["provenance"]["sources"]}
    assert statuses["USDA SSURGO"] == "failed"
    assert statuses["NASA POWER"] == "live"
    assert body["provenance"]["fawn_station"] is None


def test_degraded_live_response_preserves_integrity(sources: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "get_soil", lambda lat, lon: (_ for _ in ()).throw(TimeoutError()))
    monkeypatch.setattr(service, "get_daily_weather", lambda lat, lon: (_ for _ in ()).throw(TimeoutError()))
    response = client.get("/api/recommend", params={"lat": 29.71, "lon": -81.50})
    assert response.status_code == 200
    body = response.json()
    assert len(body["crops"]) == 13
    assert len({crop["id"] for crop in body["crops"]}) == 13
    assert all(crop["score"] is None or 0 <= crop["score"] <= 100 for crop in body["crops"])
    assert [(-(crop["score"] if crop["score"] is not None else -1), crop["name"]) for crop in body["crops"]] == sorted(
        (-(crop["score"] if crop["score"] is not None else -1), crop["name"]) for crop in body["crops"])
    assert body["provenance"]["mode"] == "live"
    assert all(source["status"] in {"live", "failed", "no data"} for source in body["provenance"]["sources"])


def test_point_in_another_state_is_rejected(sources: dict[str, Any]) -> None:
    sources["county"] = {"county": "Thomas", "county_fips": "13275", "state": "GA"}
    response = client.get("/api/recommend", params={"lat": 30.9, "lon": -84.0})
    assert response.status_code == 400
    assert response.json() == {"detail": "Location must be in Florida"}


def test_open_water_is_rejected(sources: dict[str, Any]) -> None:
    sources["county"] = None  # FCC answered: no county at this point
    response = client.get("/api/recommend", params={"lat": 27.5, "lon": -84.0})
    assert response.status_code == 400
    assert response.json() == {"detail": "Location must be in Florida"}
    assert client.get("/api/crops/potato", params={"lat": 27.5, "lon": -84.0}).status_code == 400


def test_failed_county_lookup_still_scores(sources: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(lat: float, lon: float) -> None:
        raise TimeoutError

    monkeypatch.setattr(service, "lookup_county", broken)
    body = client.get("/api/recommend", params={"lat": 29.71, "lon": -81.50}).json()
    assert body["location"]["county"] is None
    assert body["crops"][0]["factors"]["local_history"] is None
    assert any("FCC" in warning for warning in body["warnings"])


def test_outside_bounding_box() -> None:
    response = client.get("/api/recommend", params={"lat": 40.0, "lon": -74.0})
    assert response.status_code == 400
    assert response.json() == {"detail": "Location must be in Florida"}


@pytest.mark.parametrize("path", ["/api/recommend", "/api/crops/potato"])
@pytest.mark.parametrize("lat,lon", [(24.299999, -81.5), (31.100001, -81.5), (28.0, -87.700001), (28.0, -79.899999)])
def test_coordinates_outside_strict_bbox_are_rejected(path: str, lat: float, lon: float) -> None:
    response = client.get(path, params={"lat": lat, "lon": lon})
    assert response.status_code == 400


def test_oversized_crop_path_is_rejected() -> None:
    response = client.get("/api/crops/" + "x" * 65, params={"lat": 28.0, "lon": -81.5})
    assert response.status_code == 404


def test_unique_coordinates_do_not_grow_response_cache(sources: dict[str, Any]) -> None:
    service.clear_response_cache()
    for index in range(service.RESPONSE_CACHE_SIZE + 20):
        # Cache coordinates are rounded to four decimals, so these must differ
        # by at least one ten-thousandth to exercise eviction rather than hits.
        service.recommend(28.0 + index / 10000, -81.5)
    assert len(service._response_cache) == service.RESPONSE_CACHE_SIZE


def test_concurrent_recommendations_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    entered = 0
    peak = 0
    lock = threading.Lock()

    def slow_build(lat: float, lon: float, acres: float | None = None) -> tuple[dict[str, Any], bool]:
        nonlocal entered, peak
        with lock:
            entered += 1
            peak = max(peak, entered)
        time.sleep(0.02)
        with lock:
            entered -= 1
        return {"location": {"lat": lat, "lon": lon}}, True

    monkeypatch.setattr(service, "_build_recommendation", slow_build)
    service.clear_response_cache()
    with ThreadPoolExecutor(max_workers=service.MAX_CONCURRENT_RECOMMENDATIONS + 4) as pool:
        results = list(pool.map(_recommend_for_test, range(service.MAX_CONCURRENT_RECOMMENDATIONS + 4)))
    assert peak <= service.MAX_CONCURRENT_RECOMMENDATIONS
    assert "busy" in results


def _recommend_for_test(index: int) -> str:
    try:
        service.recommend(28.0 + index / 1000, -81.5)
    except service.SourcesTooSlow:
        return "busy"
    return "ok"


@pytest.mark.parametrize("lat,lon", [(float("nan"), -81.5), (28.0, float("inf")), (24.2, -81.5)])
def test_non_finite_or_outside_coordinates_are_rejected(lat: float, lon: float) -> None:
    response = client.get("/api/recommend", params={"lat": lat, "lon": lon})
    assert response.status_code == 400
    assert response.json() == {"detail": "Location must be in Florida"}


def test_crop_detail(sources: dict[str, Any]) -> None:
    body = client.get("/api/crops/potato", params={"lat": 29.71, "lon": -81.50}).json()
    assert body["id"] == "potato"
    assert (body["requirements"]["ph_ideal_min"], body["requirements"]["ph_ideal_max"]) == (5.0, 6.0)
    assert body["general_guidance"]
    assert body["extension_links"][0]["url"].startswith("https://edis.ifas.ufl.edu/")
    assert body["location"]["county"] == "St. Johns"
    assert "soil_ph" in body["conditions"]
    assert body["scoring"]["weights"]["soil_ph"] == 0.20
    assert body["limited_by"] == []


def test_crop_detail_nutrient_plan_and_lime_note(sources: dict[str, Any]) -> None:
    body = client.get("/api/crops/tomato", params={"lat": 29.71, "lon": -81.50, "acres": 1}).json()
    assert body["scale"]["fit"] == "small"
    assert body["nutrient_plan"]["n_lb_per_acre"] == 200
    assert body["nutrient_plan"]["lime_note"] == "pH 5.6 is below 6-6.8: a soil test will say how much lime is needed"
    assert len(body["nutrient_plan"]["practices"]) == 5


def test_unknown_crop() -> None:
    response = client.get("/api/crops/kale", params={"lat": 29.71, "lon": -81.50})
    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown crop"}


@pytest.mark.parametrize("path", ["/api/recommend", "/api/crops/potato"])
def test_acreage_below_minimum_is_rejected(path: str) -> None:
    params = {"lat": 29.71, "lon": -81.50, "acres": 0.09}
    response = client.get(path, params=params)
    assert response.status_code == 422


def test_cached_response_adds_small_scale_flag() -> None:
    response = {"crops": [{"id": "tomato", "name": "Tomato", "score": 90, "flags": []}]}
    updated = service._apply_acres(response, 2)
    tomato = updated["crops"][0]
    assert tomato["scale"]["fit"] == "small"
    assert tomato["score"] == 74
    assert tomato["flags"][0].startswith("Small planting of 2 acres")


def test_responses_validate_against_contract_models(sources: dict[str, Any]) -> None:
    RecommendResponse.model_validate(client.get("/api/recommend", params={"lat": 29.71, "lon": -81.50}).json())
    CropDetail.model_validate(client.get("/api/crops/potato", params={"lat": 29.71, "lon": -81.50}).json())


def test_repeat_request_served_from_memory(sources: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(service, "get_soil", lambda lat, lon: calls.append((lat, lon)) or SOIL)
    first = client.get("/api/recommend", params={"lat": 29.71, "lon": -81.50}).json()
    second = client.get("/api/recommend", params={"lat": 29.710001, "lon": -81.50}).json()
    assert len(calls) == 1
    assert second["crops"] == first["crops"]
    assert second["location"]["lat"] == 29.710001  # echoes this request, not the cached one


def test_uncached_location_builds_response(sources: dict[str, Any]) -> None:
    service.clear_response_cache()
    response = service.recommend(28.03, -82.15)
    assert len(response["crops"]) == 13
    assert response["location"]["lat"] == 28.03


def test_degraded_response_is_not_cached(sources: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def flaky(lat: float, lon: float) -> dict[str, Any]:
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError
        return SOIL

    monkeypatch.setattr(service, "get_soil", flaky)
    first = client.get("/api/recommend", params={"lat": 29.71, "lon": -81.50}).json()
    second = client.get("/api/recommend", params={"lat": 29.71, "lon": -81.50}).json()
    assert first["conditions"]["soil_ph"] is None and first["warnings"]
    assert second["conditions"]["soil_ph"] == 5.6 and second["warnings"] == []
    assert len(calls) == 2


def test_cached_response_is_not_shared_mutable_state(sources: dict[str, Any]) -> None:
    first = service.recommend(29.71, -81.50)
    first["crops"].clear()
    assert len(service.recommend(29.71, -81.50)["crops"]) == 13


def test_fractional_climate_averages_are_valid(sources: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    def frosty(lat: float, lon: float) -> pd.DataFrame:
        weather = fake_weather(lat, lon)
        weather.loc[weather.index.year == 2021, "t_min_c"] = -1.0  # one year with freezes: average is fractional
        return weather

    monkeypatch.setattr(service, "get_daily_weather", frosty)
    response = client.get("/api/recommend", params={"lat": 29.71, "lon": -81.50})
    assert response.status_code == 200
    assert response.json()["conditions"]["frost_free_days"] % 1 != 0


def test_acreage_cache_does_not_pin_small_lot_scores(sources: dict[str, Any]) -> None:
    params = {"lat": 29.71, "lon": -81.50}
    small = service.recommend(**params, acres=0.1)
    large = service.recommend(**params, acres=500)
    unspecified = service.recommend(**params)
    for crop in small["crops"]:
        if crop["id"] in {"cotton", "sugarcane", "peanut", "soybean", "field_corn"}:
            assert crop["score"] <= 40
            assert crop["scale"]["fit"] == "too_small"
        if crop["id"] in {"tomato", "strawberry", "snap_bean", "bell_pepper", "cabbage"}:
            assert crop["scale"]["fit"] == "good"
            assert "Garden-scale" in crop["scale"]["note"]
    assert {c["id"]: c["score"] for c in large["crops"]} == {c["id"]: c["score"] for c in unspecified["crops"]}
    assert all(c["scale"]["note"] is None for c in unspecified["crops"])
    service.clear_response_cache()
    fresh = service.recommend(**params)
    assert {c["id"]: c["score"] for c in fresh["crops"]} == {c["id"]: c["score"] for c in large["crops"]}


def test_minimum_acreage_is_accepted_by_both_endpoints(sources: dict[str, Any]) -> None:
    params = {"lat": 29.71, "lon": -81.50, "acres": 0.1}
    for endpoint in ("/api/recommend", "/api/crops/tomato"):
        response = client.get(endpoint, params=params)
        assert response.status_code == 200
        body = response.json()
        tomato = (next(c for c in body["crops"] if c["id"] == "tomato")
                  if "crops" in body else body)
        assert tomato["scale"]["fit"] == "good"
        assert tomato["score"] <= 74
