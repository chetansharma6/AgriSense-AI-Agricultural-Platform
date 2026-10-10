"""Judge smoke test for a running AgriSense API.

Usage: python -m scripts.smoke_test [BASE_URL]
The URL may also be supplied with SMOKE_API_URL or RENDER_API_URL.
"""

import argparse
import math
import os
import sys
import time
from typing import Any

import httpx

from app.config import DEMO_FARMS

EXPECTED_CROPS = 13
HEALTH_LIMIT_S = 5.0
RECOMMEND_LIMIT_S = 10.0
DETAIL_LIMIT_S = 10.0
VALIDATION_LIMIT_S = 5.0


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _find_bad_numbers(value: Any, path: str = "response") -> list[str]:
    if isinstance(value, float) and not math.isfinite(value):
        return [path]
    if isinstance(value, dict):
        return [bad for key, item in value.items() for bad in _find_bad_numbers(item, f"{path}.{key}")]
    if isinstance(value, list):
        return [bad for index, item in enumerate(value) for bad in _find_bad_numbers(item, f"{path}[{index}]")]
    return []


def _check_recommendation(body: Any, farm: str) -> list[str]:
    if not isinstance(body, dict):
        return [f"{farm}: response is not a JSON object"]
    crops = body.get("crops")
    if not isinstance(crops, list) or len(crops) != EXPECTED_CROPS:
        return [f"{farm}: expected exactly {EXPECTED_CROPS} crops"]
    errors: list[str] = []
    scores = [crop.get("score") if isinstance(crop, dict) else None for crop in crops]
    if any(score is not None and (not _finite(score) or not 0 <= score <= 100) for score in scores):
        errors.append(f"{farm}: score outside 0-100 or non-finite")
    comparable = [float("-inf") if score is None else score for score in scores]
    if comparable != sorted(comparable, reverse=True):
        errors.append(f"{farm}: crops are not sorted by descending score")
    bad_numbers = _find_bad_numbers(body)
    if bad_numbers:
        errors.append(f"{farm}: NaN/infinity at {bad_numbers[0]}")
    return errors


def _request(client: httpx.Client, method: str, path: str, label: str, limit: float,
             errors: list[str], **kwargs: Any) -> httpx.Response | None:
    started = time.perf_counter()
    try:
        response = client.request(method, path, **kwargs)
    except (httpx.HTTPError, ValueError) as error:
        errors.append(f"{label}: request failed ({type(error).__name__})")
        return None
    elapsed = time.perf_counter() - started
    status = "PASS" if elapsed <= limit else "FAIL"
    print(f"{status}: {label} HTTP {response.status_code} in {elapsed:.2f}s")
    if elapsed > limit:
        errors.append(f"{label}: exceeded {limit:.1f}s threshold")
    return response


def _json(response: httpx.Response, label: str, errors: list[str]) -> Any:
    try:
        return response.json()
    except ValueError:
        errors.append(f"{label}: invalid JSON response")
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test a running AgriSense backend")
    parser.add_argument("base_url", nargs="?", help="API base URL")
    args = parser.parse_args(argv)
    base_url = (args.base_url or os.getenv("SMOKE_API_URL") or os.getenv("RENDER_API_URL") or "http://localhost:8000").rstrip("/")
    errors: list[str] = []
    print(f"Testing {base_url}")
    with httpx.Client(base_url=base_url, timeout=20.0) as client:
        health = _request(client, "GET", "/api/health", "health", HEALTH_LIMIT_S, errors)
        if health is not None and (health.status_code != 200 or _json(health, "health", errors) != {"status": "ok"}):
            errors.append("health: expected HTTP 200 and {status: ok}")

        for farm, (lat, lon) in DEMO_FARMS.items():
            response = _request(client, "GET", "/api/recommend", farm, RECOMMEND_LIMIT_S, errors,
                                params={"lat": lat, "lon": lon})
            if response is not None and response.status_code == 200:
                errors.extend(_check_recommendation(_json(response, farm, errors), farm))
            elif response is not None:
                errors.append(f"{farm}: expected HTTP 200")
            detail = _request(client, "GET", "/api/crops/strawberry", f"{farm} crop detail", DETAIL_LIMIT_S, errors,
                              params={"lat": lat, "lon": lon})
            if detail is not None:
                detail_body = _json(detail, f"{farm} crop detail", errors)
                if detail.status_code != 200 or not isinstance(detail_body, dict) or detail_body.get("id") != "strawberry":
                    errors.append(f"{farm} crop detail: expected strawberry")

        for label, path, params, expected in (
            ("invalid Florida coordinate", "/api/recommend", {"lat": 24.2, "lon": -81.5}, 400),
            ("outside Florida", "/api/recommend", {"lat": 40.0, "lon": -74.0}, 400),
            ("unknown crop", "/api/crops/unknown", {"lat": 28.0, "lon": -82.0}, 404),
        ):
            response = _request(client, "GET", path, label, VALIDATION_LIMIT_S, errors, params=params)
            if response is not None and response.status_code != expected:
                errors.append(f"{label}: expected HTTP {expected}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: all smoke checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
