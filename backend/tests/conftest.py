from pathlib import Path

import pytest
import httpx

from app import cache, service
from app.clients import fawn
from app.clients import http as provider_http


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test gets an empty cache directory and an empty response cache, and no
    FAWN stations (so nothing reaches the network); FAWN tests add their own."""
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(fawn, "load_stations", lambda: ())
    service.clear_response_cache()
    return tmp_path


@pytest.fixture(autouse=True)
def forbid_unmocked_provider_network(monkeypatch: pytest.MonkeyPatch):
    """A passing offline test must not accidentally invoke a real provider."""
    attempts = []

    def unexpected(request: httpx.Request) -> httpx.Response:
        # Keep only the host: URLs may contain a private NASS API key.
        attempts.append(request.url.host)
        raise RuntimeError("Unmocked provider request in unit test")

    with httpx.Client(transport=httpx.MockTransport(unexpected)) as client:
        monkeypatch.setattr(provider_http, "_client", client)
        yield
    assert not attempts, f"Unit test reached unmocked provider hosts: {attempts}"
