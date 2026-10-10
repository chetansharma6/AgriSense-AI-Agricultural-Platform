from pathlib import Path

import pytest

from app import cache


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test gets an empty cache directory."""
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    return tmp_path
