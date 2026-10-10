from pathlib import Path

import pytest

from app import cache, service


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test gets an empty cache directory and an empty response cache."""
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    service.clear_response_cache()
    return tmp_path
