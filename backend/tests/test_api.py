"""Endpoint tests with every data source faked."""

from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import service
from app.main import app
from app.market import Market

client = TestClient(app)

COUNTY = {"county": "St. Johns", "county_fips": "12109", "state": "FL"}
SOIL = {"soil_ph": 5.6, "organic_matter_pct": 1.8, "sand_pct": 88.0, "clay_pct": 4.0,
        "texture": "sand", "drainage": "Poorly drained", "map_unit": "Test sand"}
FACTORS = {"soil_ph", "drainage", "season_temp", "frost_risk", "rainfall", "local_history"}


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
    # Like the real load_market: no county rows when the county is unknown.
    monkeypatch.setattr(service, "load_market", lambda fips: Market(None if fips is None else [], [], []))
    return fakes


def test_recommend_matches_contract(sources: dict[str, Any]) -> None:
    body = client.get("/api/recommend", params={"lat": 29.71, "lon": -81.50}).json()
    assert set(body) == {"location", "conditions", "crops", "warnings"}
    assert body["location"] == {"lat": 29.71, "lon": -81.5, "county": "St. Johns",
                                "county_fips": "12109", "state": "FL"}
    assert body["conditions"]["texture"] == "sand"
    assert body["conditions"]["frost_free_days"] == 365
    assert len(body["crops"]) == 13
    scores = [crop["score"] for crop in body["crops"]]
    assert scores == sorted(scores, reverse=True)
    for crop in body["crops"]:
        assert set(crop["factors"]) == FACTORS == set(crop["factor_details"])
        assert all(0 <= v <= 100 for v in crop["factors"].values() if v is not None)
    assert body["warnings"] == []


def test_failed_source_becomes_warning(sources: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(lat: float, lon: float) -> None:
        raise TimeoutError

    monkeypatch.setattr(service, "get_soil", broken)
    body = client.get("/api/recommend", params={"lat": 29.71, "lon": -81.50}).json()
    assert body["conditions"]["soil_ph"] is None
    assert body["crops"][0]["factors"]["soil_ph"] is None
    assert any("SSURGO" in warning for warning in body["warnings"])


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


def test_crop_detail(sources: dict[str, Any]) -> None:
    body = client.get("/api/crops/potato", params={"lat": 29.71, "lon": -81.50}).json()
    assert body["id"] == "potato"
    assert (body["requirements"]["ph_ideal_min"], body["requirements"]["ph_ideal_max"]) == (5.0, 6.0)
    assert body["general_guidance"]
    assert body["extension_links"][0]["url"].startswith("https://edis.ifas.ufl.edu/")
    assert body["location"]["county"] == "St. Johns"
    assert "soil_ph" in body["conditions"]


def test_unknown_crop() -> None:
    response = client.get("/api/crops/kale", params={"lat": 29.71, "lon": -81.50})
    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown crop"}
