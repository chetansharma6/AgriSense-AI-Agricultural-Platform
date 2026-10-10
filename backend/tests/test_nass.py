from pathlib import Path

import pytest

from app import cache
from app.clients import nass


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, url: str, params: dict) -> "FakeResponse":
        self.calls += 1
        return FakeResponse()


class FakeResponse:
    status_code = 200
    text = ""

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"data": [{"Value": "4,100"}]}


def test_query_hits_network_once_then_uses_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(nass, "nass_api_key", lambda: "test-key")
    fake = FakeClient()
    monkeypatch.setattr(nass, "_http", lambda: fake)

    params = {"commodity_desc": "PEANUTS", "state_alpha": "FL"}
    assert nass.query(params) == [{"Value": "4,100"}]
    assert nass.query(params) == [{"Value": "4,100"}]
    assert fake.calls == 1


def test_cache_file_name_never_contains_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(nass, "nass_api_key", lambda: "secret-key")
    monkeypatch.setattr(nass, "_http", lambda: FakeClient())

    nass.query({"commodity_desc": "COTTON"})
    for path in tmp_path.rglob("*"):
        assert "secret-key" not in path.name
        if path.is_file():
            assert "secret-key" not in path.read_text()
