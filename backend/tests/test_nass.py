from pathlib import Path

import pytest

from app.clients import nass
from tests.fakes import FakeClient

ROWS = [{"Value": "4,100"}]


def test_query_hits_network_once_then_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nass, "nass_api_key", lambda: "test-key")
    fake = FakeClient({"data": ROWS})
    monkeypatch.setattr(nass, "http", lambda: fake)

    params = {"commodity_desc": "PEANUTS", "state_alpha": "FL"}
    assert nass.query(params) == ROWS
    assert nass.query(params) == ROWS
    assert fake.calls == 1


def test_cache_never_contains_key(isolated_cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nass, "nass_api_key", lambda: "secret-key")
    monkeypatch.setattr(nass, "http", lambda: FakeClient({"data": ROWS}))

    nass.query({"commodity_desc": "COTTON"})
    for path in isolated_cache.rglob("*"):
        assert "secret-key" not in path.name
        if path.is_file():
            assert "secret-key" not in path.read_text()


def test_error_message_never_contains_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nass, "nass_api_key", lambda: "secret-key")
    fake = FakeClient({"error": ["bad request - invalid query"]})
    fake.status_code = 400
    monkeypatch.setattr(nass, "http", lambda: fake)

    with pytest.raises(nass.NassError) as error:
        nass.query({"commodity_desc": "NOPE"})
    assert "secret-key" not in str(error.value)
    assert "invalid query" in str(error.value)
