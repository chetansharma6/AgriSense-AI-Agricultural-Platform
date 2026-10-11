"""Provider cache admission and quota regressions."""

import math
import os
import time
from pathlib import Path

import pytest

from app import cache
from app.clients import fawn, fcc, nass, power, soil


def test_provider_validators_reject_partial_and_nonfinite_shapes() -> None:
    assert not fcc._valid_county({"county": "X", "county_fips": "12", "state": "FL"})
    assert not soil._valid_soil({"mukey": "1", "soil_ph": math.nan, "organic_matter_pct": 1,
                                 "sand_pct": 50, "clay_pct": 10, "texture": "loam", "drainage": "well"})
    assert not power._valid_series({"T2M": {}})
    assert not fawn._valid_fawn({"start": "2016-01-01", "min_c": [float("inf")]})
    assert not nass._valid_rows([{ "short_desc": "x", "statisticcat_desc": "YIELD", "domain_desc": "TOTAL",
                                   "agg_level_desc": "STATE", "reference_period_desc": "YEAR",
                                   "year": "not-year", "Value": "1"}])


def test_write_validator_rejects_bad_data_and_preserves_old_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache.write_cache("fcc", {"lat": 1}, {"county": "A", "county_fips": "12001", "state": "FL"}, fcc._valid_county)
    cache.write_cache("fcc", {"lat": 1}, {"county": "", "county_fips": "bad", "state": "FL"}, fcc._valid_county)
    assert cache.read_cache("fcc", {"lat": 1}, fcc._valid_county)["county"] == "A"


def test_quota_evicts_oldest_entry_deterministically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setitem(cache.CACHE_LIMITS, "demo", (2, 10_000))
    cache.write_cache("demo", {"n": 1}, "one")
    time.sleep(0.01)
    cache.write_cache("demo", {"n": 2}, "two")
    time.sleep(0.01)
    cache.write_cache("demo", {"n": 3}, "three")
    assert cache.read_cache("demo", {"n": 1}) is None
    assert cache.read_cache("demo", {"n": 2}) == "two"
    assert cache.read_cache("demo", {"n": 3}) == "three"


def test_provider_entries_are_key_and_namespace_isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache.write_cache("fcc", {"lat": 1}, "fcc")
    cache.write_cache("soil", {"lat": 1}, "soil")
    assert cache.read_cache("fcc", {"lat": 1}) == "fcc"
    assert cache.read_cache("soil", {"lat": 1}) == "soil"
    assert cache.read_cache("fcc", {"lat": 2}) is None


def test_stale_corrupt_and_read_only_cache_are_misses_or_nonfatal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache.write_cache("fcc", {"lat": 1}, "old")
    path = cache.cache_path("fcc", {"lat": 1})
    old = time.time() - 100
    os.utime(path, (old, old))
    assert cache.read_cache("fcc", {"lat": 1}, max_age_s=1) is None
    path.write_text("not json")
    assert cache.read_cache("fcc", {"lat": 1}) is None
    monkeypatch.setattr(cache.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("read-only")))
    cache.write_cache("fcc", {"lat": 2}, "still nonfatal")
    assert cache.read_cache("fcc", {"lat": 2}) is None
