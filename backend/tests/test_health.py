from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_configured_origin() -> None:
    response = TestClient(app).get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_allows_vercel_deployments() -> None:
    origin = "https://agrisense-git-main-team.vercel.app"
    response = TestClient(app).get("/api/health", headers={"Origin": origin})
    assert response.headers["access-control-allow-origin"] == origin


def test_cors_rejects_other_origins() -> None:
    response = TestClient(app).get("/api/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in response.headers
