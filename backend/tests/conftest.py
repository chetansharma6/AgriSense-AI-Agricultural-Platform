from pathlib import Path

import pytest

from app import cache, service
from app.clients import fawn


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test gets an empty cache directory and an empty response cache, and no
    FAWN stations (so nothing reaches the network); FAWN tests add their own."""
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(fawn, "load_stations", lambda: ())
    service.clear_response_cache()
    return tmp_path
