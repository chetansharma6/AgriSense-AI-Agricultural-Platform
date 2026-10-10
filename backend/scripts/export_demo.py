"""Save real API responses for the demo farms to data/demo/<farm>.json.

Frontend mocks for use before integration. Start the server first, then from backend/:
    python -m scripts.export_demo [base_url]

Each file is {"recommend": <response>, "crops": {"<id>": <crop detail response>, ...}} for all 13 crops.
"""

import json
import sys

import httpx

from app.config import DATA_DIR, DEMO_FARMS


def main(base_url: str) -> None:
    out_dir = DATA_DIR / "demo"
    with httpx.Client(base_url=base_url, timeout=180) as client:
        for farm, (lat, lon) in DEMO_FARMS.items():
            params = {"lat": lat, "lon": lon}
            recommend = client.get("/api/recommend", params=params).raise_for_status().json()
            crops = {crop["id"]: client.get(f"/api/crops/{crop['id']}", params=params).raise_for_status().json()
                     for crop in recommend["crops"]}
            path = out_dir / f"{farm}.json"
            path.write_text(json.dumps({"recommend": recommend, "crops": crops}, indent=2) + "\n")
            top = recommend["crops"][0]
            print(f"{path.relative_to(DATA_DIR.parent)}: {len(crops)} crops, top {top['name']} {top['score']}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000")
