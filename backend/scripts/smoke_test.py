"""Judge smoke test for a running AgriSense API.

Usage: python -m scripts.smoke_test [base-url]
The default is http://localhost:8000; SMOKE_API_URL may also provide a URL.
"""

import math
import os
import sys
from typing import Any

import httpx

from app.config import DEMO_FARMS


def check_response(body: dict[str, Any], farm: str) -> list[str]:
    errors: list[str] = []
    crops = body.get("crops")
    if not isinstance(crops, list) or len(crops) != 13:
        errors.append(f"{farm}: expected 13 crops")
    scores = [crop.get("score") for crop in crops or []]
    if any(score is not None and (not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 100)
           for score in scores):
        errors.append(f"{farm}: invalid score")
    if scores != sorted(scores, key=lambda score: float("inf") if score is None else -score):
        errors.append(f"{farm}: crops are not sorted")
    if body.get("confidence", {}).get("total_factors") != 6:
        errors.append(f"{farm}: missing confidence metadata")
    if not body.get("provenance"):
        errors.append(f"{farm}: missing provenance metadata")
    return errors


def main() -> int:
    base_url = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("SMOKE_API_URL", "http://localhost:8000")).rstrip("/")
    errors: list[str] = []
    with httpx.Client(base_url=base_url, timeout=20) as client:
        response = client.get("/api/health")
        if response.status_code != 200 or response.json() != {"status": "ok"}:
            errors.append(f"health: HTTP {response.status_code}")
        for farm, (lat, lon) in DEMO_FARMS.items():
            response = client.get("/api/recommend", params={"lat": lat, "lon": lon})
            if response.status_code != 200:
                errors.append(f"{farm}: HTTP {response.status_code}")
                continue
            errors.extend(check_response(response.json(), farm))
            detail = client.get("/api/crops/strawberry", params={"lat": lat, "lon": lon})
            if detail.status_code != 200 or detail.json().get("id") != "strawberry":
                errors.append(f"{farm}: crop detail failed ({detail.status_code})")
        for path, params, expected in (
            ("/api/recommend", {"lat": 40, "lon": -74}, 400),
            ("/api/crops/unknown", {"lat": 28, "lon": -82}, 404),
        ):
            if client.get(path, params=params).status_code != expected:
                errors.append(f"{path}: expected HTTP {expected}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: {base_url} health, four demo farms, crop details, and validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
