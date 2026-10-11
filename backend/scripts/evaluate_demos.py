"""Offline evaluator for the four committed AgriSense demo responses.

Run from backend/: python -m scripts.evaluate_demos
Exit status is zero only when every demo satisfies all evaluation checks.
"""

import json
import math
import sys
import time
from contextlib import ExitStack
from typing import Any
from unittest.mock import patch

from app import config, service
from app.schemas import CropDetail, RawDemoFixture, RecommendResponse

EXPECTED_CROPS = 13
MAX_LATENCY_MS = 1_000.0
PROVIDER_CALLS = (
    "lookup_county", "get_soil", "get_daily_weather", "load_market",
)


def _bad_numbers(value: Any, path: str = "response") -> list[str]:
    if isinstance(value, float) and not math.isfinite(value):
        return [path]
    if isinstance(value, dict):
        return [bad for key, child in value.items() for bad in _bad_numbers(child, f"{path}.{key}")]
    if isinstance(value, list):
        return [bad for index, child in enumerate(value) for bad in _bad_numbers(child, f"{path}[{index}]")]
    return []


def _evaluate(name: str, response: dict[str, Any], repeated: dict[str, Any],
              latency_ms: float) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    crops = response.get("crops")
    if not isinstance(crops, list):
        crops = []
        errors.append(f"{name}: crops is not a list")
    scores = [crop.get("score") for crop in crops if isinstance(crop, dict)]
    numeric_scores = [score for score in scores if isinstance(score, (int, float)) and not isinstance(score, bool)]
    score_range = [min(numeric_scores), max(numeric_scores)] if numeric_scores else [None, None]
    ordering = scores == sorted(scores, key=lambda score: float("-inf") if score is None else score, reverse=True)
    missing = sorted({factor for crop in crops if isinstance(crop, dict)
                      for factor, value in (crop.get("factors") or {}).items() if value is None})
    provenance = response.get("provenance") or {}
    sources = provenance.get("sources") if isinstance(provenance, dict) else None
    source_status = ({source.get("name"): source.get("status") for source in sources
                      if isinstance(source, dict)} if isinstance(sources, list) else {})
    bad_numbers = _bad_numbers(response)
    deterministic = response == repeated

    try:
        RecommendResponse.model_validate(response)
    except Exception as error:
        errors.append(f"{name}: public recommendation contract invalid ({type(error).__name__})")

    if latency_ms >= MAX_LATENCY_MS:
        errors.append(f"{name}: latency {latency_ms:.1f} ms exceeds {MAX_LATENCY_MS:.0f} ms")
    if len(crops) != EXPECTED_CROPS:
        errors.append(f"{name}: expected {EXPECTED_CROPS} crops, got {len(crops)}")
    if len(numeric_scores) != len(crops) or any(not 0 <= score <= 100 for score in numeric_scores):
        errors.append(f"{name}: scores must be finite numbers from 0 to 100")
    if not ordering:
        errors.append(f"{name}: crop scores are not ordered descending")
    if bad_numbers:
        errors.append(f"{name}: NaN/infinity at {bad_numbers[0]}")
    if not deterministic:
        errors.append(f"{name}: repeated response changed")
    if provenance.get("mode") != "demo" or len(source_status) != 4:
        errors.append(f"{name}: provenance must identify four demo sources")

    report = {
        "latency_ms": round(latency_ms, 1), "crop_count": len(crops),
        "score_range": score_range, "ordering": ordering,
        "missing_factors": missing, "source_status": source_status,
        "deterministic": deterministic, "finite": not bad_numbers,
    }
    return report, errors


def _evaluate_fixture(name: str) -> list[str]:
    """Validate the committed raw source fixture before service decoration."""
    path = config.DATA_DIR / "demo" / f"{name}.json"
    try:
        fixture = RawDemoFixture.model_validate(json.loads(path.read_text()))
    except Exception as error:
        return [f"{name}: raw fixture invalid ({type(error).__name__})"]
    expected_ids = set(service.load_crops())
    if {crop.id for crop in fixture.recommend.crops} != expected_ids:
        return [f"{name}: raw fixture recommendation crop ids do not match committed crops"]
    if set(fixture.crops) != expected_ids:
        return [f"{name}: raw fixture detail crop ids do not match committed crops"]
    return []


def _evaluate_details(name: str, lat: float, lon: float) -> list[str]:
    """Validate every API-equivalent detail response without provider access."""
    errors: list[str] = []
    for crop_id in service.load_crops():
        try:
            detail = service.crop_detail(crop_id, lat, lon)
            if detail is None:
                errors.append(f"{name}: detail missing for {crop_id}")
                continue
            CropDetail.model_validate(detail)
            bad_numbers = _bad_numbers(detail, f"{name}.crops.{crop_id}")
            if bad_numbers:
                errors.append(f"{name}: detail NaN/infinity at {bad_numbers[0]}")
        except Exception as error:
            errors.append(f"{name}: detail {crop_id} invalid ({type(error).__name__})")
    return errors


def _forbid_network(*_args: Any, **_kwargs: Any) -> None:
    raise AssertionError("demo evaluation attempted an external provider call")


def run() -> tuple[dict[str, dict[str, Any]], list[str]]:
    reports: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    previous_demo_mode = config.DEMO_MODE
    config.DEMO_MODE = True
    service.clear_response_cache()
    try:
        with ExitStack() as stack:
            for target in PROVIDER_CALLS:
                stack.enter_context(patch.object(service, target, _forbid_network))
            stack.enter_context(patch.object(service.fawn, "nearest_station", _forbid_network))
            stack.enter_context(patch.object(service.fawn, "daily_min_c", _forbid_network))
            for name, (lat, lon) in config.DEMO_FARMS.items():
                try:
                    errors.extend(_evaluate_fixture(name))
                    started = time.perf_counter()
                    response = service.recommend(lat, lon)
                    latency_ms = (time.perf_counter() - started) * 1_000
                    repeated = service.recommend(lat, lon)
                    report, failures = _evaluate(name, response, repeated, latency_ms)
                    reports[name] = report
                    errors.extend(failures)
                    errors.extend(_evaluate_details(name, lat, lon))
                except Exception as error:
                    errors.append(f"{name}: evaluation failed ({type(error).__name__}: {error})")
    finally:
        config.DEMO_MODE = previous_demo_mode
        service.clear_response_cache()
    return reports, errors


def main() -> int:
    reports, errors = run()
    for name, report in reports.items():
        print(f"{name}: {json.dumps(report, sort_keys=True)}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: all four committed demo responses passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
