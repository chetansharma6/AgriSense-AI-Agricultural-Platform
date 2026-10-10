from fastapi.testclient import TestClient
import pytest

from app import config
from app.main import app
from app.schemas import CropDetail, RecommendResponse


def test_health() -> None:
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_configured_origin() -> None:
    response = TestClient(app).get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_allows_production_website() -> None:
    origin = "https://agrisense-ai-cyan.vercel.app"
    response = TestClient(app).get("/api/health", headers={"Origin": origin})
    assert response.headers["access-control-allow-origin"] == origin


def test_cors_rejects_unapproved_vercel_deployments() -> None:
    origin = "https://agrisense-git-main-team.vercel.app"
    response = TestClient(app).get("/api/health", headers={"Origin": origin})
    assert "access-control-allow-origin" not in response.headers


def test_recommend_preflight_matches_frontend_request() -> None:
    origin = "https://agrisense-ai-cyan.vercel.app"
    client = TestClient(app)
    path = "/api/recommend?lat=29.71&lon=-81.5&acres=0.1"
    headers = {"Origin": origin, "Access-Control-Request-Method": "GET",
               "Access-Control-Request-Headers": "content-type"}
    response = client.options(path, headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"]
    headers["Origin"] = "https://unapproved.vercel.app"
    assert client.options(path, headers=headers).status_code == 400
    headers["Origin"] = origin
    headers["Access-Control-Request-Method"] = "POST"
    assert client.options(path, headers=headers).status_code == 400


def test_cors_rejects_other_origins() -> None:
    response = TestClient(app).get("/api/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("acres", [None, 0.1, 7, 1000])
def test_browser_request_preserves_acreage_and_response_contract(monkeypatch, acres) -> None:
    monkeypatch.setattr(config, "DEMO_MODE", True)
    params = {"lat": 29.71, "lon": -81.5}
    if acres is not None:
        params["acres"] = acres
    headers = {"Origin": config.PRODUCTION_ORIGIN}
    client = TestClient(app)
    response = client.get("/api/recommend", params=params, headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == config.PRODUCTION_ORIGIN
    body = RecommendResponse.model_validate(response.json())
    cotton = next(crop for crop in body.crops if crop.id == "cotton")
    if acres is None:
        assert cotton.scale.fit is None
    elif acres < 500:
        assert cotton.scale.fit == "too_small"
        assert cotton.score <= 40
    else:
        assert cotton.scale.fit == "good"
    detail_response = client.get("/api/crops/cotton", params=params, headers=headers)
    assert detail_response.status_code == 200
    detail = CropDetail.model_validate(detail_response.json())
    assert detail.score == cotton.score
    assert detail.scale == cotton.scale
    assert detail.provenance.mode == "demo"
