"""Provider failure matrix: failures stay bounded, classified, and private."""

import httpx
import pytest

from app import cache, service
from app.clients import fawn, power


class ErrorClient:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def get(self, *_args: object, **_kwargs: object) -> object:
        self.calls += 1
        raise self.error

    post = get


@pytest.mark.parametrize("error", [httpx.ConnectError("provider down"), httpx.ReadError("broken stream")])
def test_power_transport_failures_are_provider_errors(monkeypatch: pytest.MonkeyPatch, error: httpx.HTTPError) -> None:
    client = ErrorClient(error)
    monkeypatch.setattr(power, "http", lambda: client)

    with pytest.raises(power.PowerError, match="request failed"):
        power.get_daily_weather(29.71, -81.50)
    assert client.calls == 1


@pytest.mark.parametrize("error", [httpx.ConnectError("provider down"), httpx.ReadError("broken stream")])
def test_fawn_transport_failures_are_provider_errors(monkeypatch: pytest.MonkeyPatch, error: httpx.HTTPError) -> None:
    monkeypatch.setattr(fawn, "read_cache", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(fawn, "write_cache", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("read-only")))
    client = ErrorClient(error)
    monkeypatch.setattr(fawn, "http", lambda: client)

    with pytest.raises(fawn.FawnError, match="request failed"):
        fawn._download("270")
    assert client.calls == 1


def test_fawn_invalid_numeric_rows_are_discarded_without_secret_leakage() -> None:
    report = (
        '"FAWN Station","Period","2m T avg (F)","2m T min (F)","2m T max (F)","N (# obs)"\n'
        '"Hastings","25 Jan 2022","bad","not-a-number","60.39","96"\n'
    )
    assert fawn.parse_report(report) == {}


def test_provider_failure_becomes_provenance_warning() -> None:
    warnings: list[str] = []
    failed: list[str] = []
    result = service._attempt(lambda: (_ for _ in ()).throw(httpx.ConnectError("secret-key")),
                              "NASA POWER", warnings, failed)

    assert result is None
    assert failed == ["NASA POWER"]
    assert warnings == ["NASA POWER unavailable (ConnectError); related values are null"]
    assert "secret-key" not in " ".join(warnings)


def test_cache_write_failure_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("full disk")))
    cache.write_cache("matrix", {"provider": "POWER"}, {"ok": True})
