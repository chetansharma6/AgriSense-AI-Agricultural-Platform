"""Regressions found during the final backend reliability audit."""

import copy
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest
import anyio
import httpx

from app import config, service


def response() -> dict:
    result = service._deadline_response(27.945, -82.4583, "test")
    result["location"].update(county="Hillsborough", county_fips="12057")
    result["warnings"] = []
    for crop in result["crops"]:
        crop["score"] = 100
    return result


def test_shared_build_preserves_scores_and_request_coordinates(monkeypatch) -> None:
    shared = response()
    original = copy.deepcopy(shared)
    monkeypatch.setattr(config, "DEMO_MODE", False)
    monkeypatch.setattr(service, "_coalesced_build", lambda *_: (shared, False))
    small = service.recommend(27.9449854, -82.4583107, 0.5)
    large = service.recommend(27.94501, -82.45831, 1000)
    assert shared == original
    cotton = next(crop for crop in large["crops"] if crop["id"] == "cotton")
    assert cotton["score"] == 100
    assert small["location"]["lat"] == 27.9449854
    assert large["location"]["lat"] == 27.94501


def test_cached_requests_remain_available_when_live_slots_are_full(monkeypatch) -> None:
    monkeypatch.setattr(config, "DEMO_MODE", False)
    service._remember(service._cache_key(27.945, -82.4583), response())
    acquired = 0
    try:
        while service._recommendation_slots.acquire(blocking=False):
            acquired += 1
        assert service.recommend(27.945, -82.4583)["location"]["county"] == "Hillsborough"
    finally:
        for _ in range(acquired):
            service._recommendation_slots.release()


def test_county_timeout_is_partial_data_not_outside_florida(monkeypatch) -> None:
    partial = service._deadline_response(27.945, -82.4583, "County lookup (FCC) timed out; related values are null")
    monkeypatch.setattr(config, "DEMO_MODE", False)
    monkeypatch.setattr(service, "_coalesced_build", lambda *_: (partial, False))
    result = service.recommend(27.945, -82.4583)
    assert result["location"]["county"] is None
    assert len(result["crops"]) == 13


def test_late_provider_failure_does_not_mutate_returned_warnings() -> None:
    gate = threading.Event()
    finished = threading.Event()
    warnings: list[str] = []
    failed: list[str] = []

    def slow() -> None:
        try:
            assert gate.wait(1)
            raise TimeoutError("late failure")
        finally:
            finished.set()

    service._bounded_fetches({"Soil": slow}, time.perf_counter() + 0.02, warnings, failed)
    snapshot = (warnings.copy(), failed.copy())
    gate.set()
    assert finished.wait(1)
    # The worker must have finished its exception classification too.
    time.sleep(0.01)
    assert (warnings, failed) == snapshot


@pytest.mark.parametrize("raw", ["inf", "nan", "-inf", "0", "-1", "bad"])
def test_deadline_setting_must_be_positive_and_finite(monkeypatch, raw: str) -> None:
    monkeypatch.setenv("RECOMMENDATION_DEADLINE_S", raw)
    assert config._positive_float("RECOMMENDATION_DEADLINE_S", 6.0) == 6.0


def test_concurrent_followers_share_one_build_without_acreage_leaks(monkeypatch) -> None:
    monkeypatch.setattr(config, "DEMO_MODE", False)
    monkeypatch.setattr(config, "RECOMMENDATION_DEADLINE_S", 2.0)
    started = threading.Event()
    release = threading.Event()
    builds = []

    def build(*_) -> tuple[dict, bool]:
        builds.append(1)
        started.set()
        assert release.wait(1)
        return response(), True

    monkeypatch.setattr(service, "_build_recommendation_bounded", build)
    with ThreadPoolExecutor(max_workers=32) as pool:
        leader = pool.submit(service.recommend, 27.945, -82.4583, 0.5)
        assert started.wait(1)
        followers = [pool.submit(service.recommend, 27.945, -82.4583, 1000) for _ in range(31)]
        release.set()
        small = leader.result(timeout=2)
        results = [future.result(timeout=2) for future in followers]
    assert len(builds) == 1
    assert next(crop for crop in small["crops"] if crop["id"] == "cotton")["score"] < 100
    assert all(next(crop for crop in result["crops"] if crop["id"] == "cotton")["score"] == 100
               for result in results)
    assert service.recommend(27.945, -82.4583, 1000)["crops"] == results[-1]["crops"]


def test_health_bypasses_saturated_sync_workers() -> None:
    from app.main import app

    async def exercise() -> None:
        limiter = anyio.to_thread.current_default_thread_limiter()
        previous = limiter.total_tokens
        limiter.total_tokens = 1
        started = threading.Event()
        release = threading.Event()

        def blocked_work() -> None:
            started.set()
            release.wait(1)

        busy = asyncio.create_task(anyio.to_thread.run_sync(blocked_work))
        try:
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(0.001)
            assert started.is_set()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                result = await asyncio.wait_for(client.get("/api/health"), timeout=0.2)
            assert result.status_code == 200
        finally:
            release.set()
            await busy
            limiter.total_tokens = previous

    asyncio.run(exercise())
