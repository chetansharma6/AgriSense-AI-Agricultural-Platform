"""Save real API responses for the demo farms to data/demo/<farm>.json.

These are the DEMO_MODE fallback responses and the frontend's mocks. Fetching
them also warms the soil, weather, county and NASS caches. From backend/:
    python -m scripts.export_demo              # in-process, no server needed
    python -m scripts.export_demo <base_url>   # from a running server

Each file is {"recommend": <response>, "crops": {"<id>": <crop detail response>, ...}} for all 13 crops.
"""

import json
import sys

import httpx
from fastapi.testclient import TestClient

from app import config
from app.config import DATA_DIR, DEMO_FARMS
from app.main import app


def main(base_url: str | None) -> None:
    # Always live data: a DEMO_MODE fallback must never be saved as a demo response.
    config.DEMO_MODE = False
    out_dir = DATA_DIR / "demo"
    with (httpx.Client(base_url=base_url, timeout=180) if base_url else TestClient(app)) as client:
        for farm, (lat, lon) in DEMO_FARMS.items():
            params = {"lat": lat, "lon": lon}
            recommend = client.get("/api/recommend", params=params).raise_for_status().json()
            failures = [w for w in recommend["warnings"] if "unavailable" in w or w.startswith("Showing cached data")]
            if failures:
                raise SystemExit(f"{farm}: a data source failed, not saved: {failures}")
            crops = {crop["id"]: client.get(f"/api/crops/{crop['id']}", params=params).raise_for_status().json()
                     for crop in recommend["crops"]}
            path = out_dir / f"{farm}.json"
            path.write_text(json.dumps({"recommend": recommend, "crops": crops}, indent=2) + "\n")
            top = recommend["crops"][0]
            print(f"{path.relative_to(DATA_DIR.parent)}: {len(crops)} crops, top {top['name']} {top['score']}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
