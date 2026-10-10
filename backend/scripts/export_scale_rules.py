"""Export fallback acreage bands from the Python scorer; no upstream data fetches.

Run from backend/: python -m scripts.export_scale_rules
"""

import json
from pathlib import Path
from typing import Any

from app.crops import load_crops
from app.scoring import scale_adjusted_score, scale_info


def scale_rules() -> dict[str, list[dict[str, Any]]]:
    """Serialize every decision interval, including its score cap and note."""
    result = {}
    for crop in load_crops().values():
        boundaries = sorted({0.0, 1.0, crop.small_acres, crop.min_practical_acres, 10001.0})
        bands = []
        for lower, upper in zip(boundaries, boundaries[1:]):
            acres = (lower + upper) / 2
            scale = scale_info(crop, acres)
            if scale["note"]:
                scale["note"] = scale["note"].replace(f"{acres:g} acres", "{acres} acres")
            bands.append({"below": upper, "scale": scale,
                          "cap": scale_adjusted_score(100, crop, acres)})
        result[crop.id] = bands
    return result


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[2] / "frontend/src/mocks/scale-rules.json"
    target.write_text(json.dumps(scale_rules(), indent=2) + "\n")
