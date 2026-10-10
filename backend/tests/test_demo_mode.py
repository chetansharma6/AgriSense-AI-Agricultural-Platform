import pytest

from app import cache, config
from app.clients import fcc, http


def test_demo_mode_blocks_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "DEMO_MODE", True)
    with pytest.raises(http.OfflineMode):
        http.http()


def test_demo_mode_still_serves_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    county = {"county": "St. Johns", "county_fips": "12109", "state": "FL"}
    cache.write_cache("fcc", {"lat": 29.71, "lon": -81.5}, county)
    monkeypatch.setattr(config, "DEMO_MODE", True)
    assert fcc.lookup_county(29.71, -81.50) == county
