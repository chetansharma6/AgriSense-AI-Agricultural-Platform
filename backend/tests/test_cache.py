from pathlib import Path

import pytest

from app import cache


def test_write_then_read_leaves_no_temp_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache.write_cache("demo", {"a": 1}, [{"x": 2}])
    assert cache.read_cache("demo", {"a": 1}) == [{"x": 2}]
    assert not list(tmp_path.rglob("*.tmp"))


def test_failed_write_keeps_old_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache.write_cache("demo", {"a": 1}, "old")
    with pytest.raises(TypeError):
        cache.write_cache("demo", {"a": 1}, object())
    assert cache.read_cache("demo", {"a": 1}) == "old"
    assert not list(tmp_path.rglob("*.tmp"))
