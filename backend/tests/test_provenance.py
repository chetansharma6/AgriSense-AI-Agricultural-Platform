from urllib.parse import urlparse

from app import service
from app import config
from app.market import load_market
from app.schemas import Provenance


def test_provenance_has_safe_public_source_metadata() -> None:
    provenance = Provenance.model_validate(service._provenance("live"))
    assert len(provenance.sources) == 4
    for source in provenance.sources:
        parsed = urlparse(source.url)
        assert parsed.scheme == "https"
        assert parsed.netloc
        assert source.data_period
        assert source.data_status == "live"
        assert source.geographic_level
        assert source.limitations
        assert "secret" not in repr(source).lower()
        assert "/workspaces/" not in repr(source)


def test_demo_and_cached_statuses_are_explicit() -> None:
    demo = service._provenance("demo")
    cached = service._provenance("live", detail="Memory cache", cache_status="cached")
    assert {source["data_status"] for source in demo["sources"]} == {"demo"}
    assert {source["data_status"] for source in cached["sources"]} == {"cached"}


def test_failed_source_has_failure_status_without_provider_error_text() -> None:
    provenance = service._provenance("live", failed=["NASA POWER (ConnectError: secret-token)"])
    power = next(source for source in provenance["sources"] if source["name"] == "NASA POWER")
    assert power["status"] == "failed"
    assert power["data_status"] == "live"
    assert "secret-token" not in repr(provenance)


def test_historical_market_is_labelled_and_survives_memory_cache(monkeypatch) -> None:
    monkeypatch.setattr(config, "NASS_USE_SNAPSHOT", True)
    monkeypatch.setattr(config, "DEMO_MODE", False)
    market = load_market("12057")
    result = service._deadline_response(27.945, -82.4583, "partial")
    result["location"].update(county="Hillsborough", county_fips="12057")
    station = ({"name": "Test station"}, 12.3)
    result["provenance"] = service._provenance("live", market=market, station=station)
    source = next(source for source in result["provenance"]["sources"] if source["name"] == "USDA NASS")
    assert source["status"] == "saved"
    assert source["data_period"] == market.data_period
    service._remember(service._cache_key(27.945, -82.4583), result)
    cached = service.recommend(27.945, -82.4583)
    source = next(source for source in cached["provenance"]["sources"] if source["name"] == "USDA NASS")
    assert source["status"] == "saved" and source["data_status"] == "cached"
    assert "historical export" in source["detail"]
    assert cached["provenance"]["fawn_station"] == {"name": "Test station", "distance_km": 12.3}
