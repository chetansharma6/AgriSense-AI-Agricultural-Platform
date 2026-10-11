"""Regression coverage for the bounded recommendation-provider pipeline."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import time

from app import config, service


def test_eight_unique_requests_share_global_provider_limit() -> None:
    active = 0
    peak = 0
    lock = threading.Lock()
    gate = threading.Barrier(8)

    def fetch() -> str:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.04)
        with lock:
            active -= 1
        return "ok"

    def request(_: int) -> None:
        gate.wait()
        warnings: list[str] = []
        failed: list[str] = []
        result = service._bounded_fetches({"test provider": fetch}, time.perf_counter() + 1,
                                          warnings, failed)
        assert result == {"test provider": "ok"}

    with ThreadPoolExecutor(max_workers=8) as callers:
        list(callers.map(request, range(8)))
    assert peak <= service.MAX_CONCURRENT_PROVIDER_WORK


def test_identical_coordinates_share_one_inflight_pipeline(monkeypatch) -> None:
    calls = 0
    calls_lock = threading.Lock()
    gate = threading.Barrier(4)

    def build(lat: float, lon: float, deadline: float):
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.04)
        return service._deadline_response(lat, lon, "test partial"), False

    monkeypatch.setattr(config, "DEMO_MODE", False)
    monkeypatch.setattr(service, "_build_recommendation_bounded", build)

    def request() -> None:
        gate.wait()
        result, complete = service._coalesced_build((28.5, -81.4), 28.5, -81.4, time.perf_counter() + 1)
        assert not complete
        assert result["location"]["lat"] == 28.5

    with ThreadPoolExecutor(max_workers=4) as callers:
        list(callers.map(lambda _: request(), range(4)))
    assert calls == 1


def test_deadline_returns_partial_and_does_not_leave_work_queued() -> None:
    started = time.perf_counter()
    warnings: list[str] = []
    failed: list[str] = []

    def slow() -> None:
        time.sleep(0.2)

    result = service._bounded_fetches({"NASA POWER": slow}, started + 0.02, warnings, failed)
    assert time.perf_counter() - started < 0.12
    assert result == {"NASA POWER": None}
    assert failed == ["NASA POWER"]
    assert warnings == ["NASA POWER timed out; related values are null"]


def test_dependent_market_starts_before_slow_weather_finishes() -> None:
    weather_started = threading.Event()
    market_started = threading.Event()

    def weather() -> str:
        weather_started.set()
        assert market_started.wait(0.5)
        return "weather"

    def county() -> str:
        assert weather_started.wait(0.5)
        return "12057"

    def market(fips: str) -> str:
        market_started.set()
        return fips

    warnings: list[str] = []
    failed: list[str] = []
    result = service._bounded_fetches(
        {"county": county, "weather": weather}, time.perf_counter() + 1,
        warnings, failed, dependent={"market": ("county", market)},
    )
    assert result == {"county": "12057", "weather": "weather", "market": "12057"}
    assert warnings == failed == []


def test_no_private_concurrent_futures_internals() -> None:
    source = (Path(service.__file__).read_text())
    for private_name in ("from concurrent.futures.thread", "def _adjust_thread_count", "_threads_queues"):
        assert private_name not in source

