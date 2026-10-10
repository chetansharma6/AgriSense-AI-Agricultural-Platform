"""The frontend fallback must follow the normal scorer at every acreage boundary."""

import json
from pathlib import Path

from app.crops import load_crops
from app.scoring import scale_adjusted_score, scale_info
from scripts.export_scale_rules import scale_rules


def test_committed_scale_rules_match_python_scorer() -> None:
    path = Path(__file__).resolve().parents[2] / "frontend/src/mocks/scale-rules.json"
    rules = json.loads(path.read_text())
    assert rules == scale_rules()
    for crop in load_crops().values():
        values = {0.1, 0.25, 0.5, 0.99, 1, 3, 7, 100, 500, 10000,
                  crop.small_acres, crop.min_practical_acres}
        values.update(value - 0.001 for value in list(values) if value > 0.1)
        for acres in values:
            band = next(b for b in rules[crop.id] if acres < b["below"])
            scale = dict(band["scale"])
            if scale["note"]:
                scale["note"] = scale["note"].replace("{acres}", f"{acres:g}")
            assert scale == scale_info(crop, acres)
            assert band["cap"] == scale_adjusted_score(100, crop, acres)
