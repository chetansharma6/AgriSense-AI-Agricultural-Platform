from pathlib import Path
from typing import Any

import pytest
import httpx

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
    # This deliberately partial fixture is usable by this unit test but is not
    # admissible as a future market-cache row.
    assert fake.calls == 2


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


def test_malformed_json_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    class Malformed(FakeClient):
        def get(self, url: str, **kwargs: Any) -> Any:
            self.calls += 1
            response = super().get(url, **kwargs)
            response.json = lambda: (_ for _ in ()).throw(ValueError("not json"))
            return response

    monkeypatch.setattr(nass, "nass_api_key", lambda: "test-key")
    monkeypatch.setattr(nass, "http", lambda: Malformed({}))
    with pytest.raises(nass.NassError, match="malformed"):
        nass.query({"commodity_desc": "PEANUTS"})


@pytest.mark.parametrize("error", [httpx.ReadTimeout("secret-key"), httpx.ConnectError("secret-key")])
def test_transport_errors_do_not_expose_credentials(monkeypatch: pytest.MonkeyPatch, error: httpx.HTTPError) -> None:
    monkeypatch.setattr(nass, "nass_api_key", lambda: "secret-key")

    class BrokenClient:
        def get(self, url: str, **kwargs: Any) -> Any:
            raise error

    monkeypatch.setattr(nass, "http", lambda: BrokenClient())
    with pytest.raises(nass.NassError) as raised:
        nass.query({"commodity_desc": "PEANUTS"})
    assert "secret-key" not in str(raised.value)
    assert "NASS" in str(raised.value)
