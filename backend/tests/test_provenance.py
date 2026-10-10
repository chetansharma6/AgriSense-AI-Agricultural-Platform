from urllib.parse import urlparse

from app import service
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
