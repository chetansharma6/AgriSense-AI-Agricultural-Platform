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
    cache.write_cache("demo", {"a": 1}, object())
    assert cache.read_cache("demo", {"a": 1}) == "old"
    assert not list(tmp_path.rglob("*.tmp"))


def test_read_only_cache_dir_skips_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "demo").mkdir()
    for directory in (tmp_path, tmp_path / "demo"):
        directory.chmod(0o555)
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    try:
        cache.write_cache("demo", {"a": 1}, "value")  # no exception
        cache.write_cache("new_namespace", {"a": 1}, "value")  # cannot even create the folder
        assert cache.read_cache("demo", {"a": 1}) is None
    finally:
        for directory in (tmp_path, tmp_path / "demo"):
            directory.chmod(0o755)


def test_read_only_cache_still_serves_existing_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache.write_cache("demo", {"a": 1}, "value")
    for path in tmp_path.rglob("*"):
        path.chmod(0o555 if path.is_dir() else 0o444)
    try:
        assert cache.read_cache("demo", {"a": 1}) == "value"
    finally:
        for path in tmp_path.rglob("*"):
            path.chmod(0o755)


def test_corrupt_entry_is_a_miss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache.write_cache("demo", {"a": 1}, "value")
    cache.cache_path("demo", {"a": 1}).write_text('{"truncated')
    assert cache.read_cache("demo", {"a": 1}) is None
    cache.write_cache("demo", {"a": 1}, "fresh")
    assert cache.read_cache("demo", {"a": 1}) == "fresh"
