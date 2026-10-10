"""Refresh frontend fixtures from saved backend data and Python acreage rules."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
MOCKS = ROOT / "frontend/src/mocks"
# Execute only pure backend helpers, without importing network clients.
tree = ast.parse((BACKEND / "app/scoring.py").read_text())
helpers = ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef)
                          and node.name in {"scale_info", "estimated_gross_value"}], type_ignores=[])
namespace = {"Crop": object, "Any": object}
exec(compile(helpers, "backend/app/scoring.py", "exec"), namespace)
requirements = {crop["id"]: crop for crop in json.loads((BACKEND / "data/crops.json").read_text())}
variants = {}
for farm in ("marianna", "hastings", "plant_city", "belle_glade"):
    sample = json.loads((BACKEND / f"data/demo/{farm}.json").read_text())
    for result in [*sample["recommend"]["crops"], *sample["crops"].values()]:
        crop = requirements[result["id"]]
        result["scale"] = namespace["scale_info"](SimpleNamespace(**crop), None)
        result["est_gross_value"] = None
        if "requirements" in result:
            result["requirements"] = crop
            ph = result["conditions"].get("soil_ph")
            result["nutrient_plan"] = {
                "n_lb_per_acre": crop["n_lb_per_acre"], "soil_test_first": True,
                "lime_note": f"pH {ph:g} is below {crop['ph_ideal_min']:g}-{crop['ph_ideal_max']:g}: a soil test will say how much lime is needed" if ph is not None and ph < crop["ph_ideal_min"] else None,
                "practices": ["Soil test before fertilizing", "Split nitrogen into several smaller applications", "Consider controlled-release fertilizer or fertigation through drip lines", "Use cover crops and compost to build organic matter on sandy soils", "Follow Florida agricultural Best Management Practices (FDACS)"],
                "sources": [crop["nutrient_source"], {"title": "UF/IFAS 4R nutrient management", "url": "https://edis.ifas.ufl.edu/publication/SS639"}, {"title": "FDACS Agricultural Best Management Practices", "url": "https://www.fdacs.gov/Water/Agricultural-Water-Field-Services/Agricultural-Best-Management-Practices"}],
            }
    (MOCKS / f"{farm}.json").write_text(json.dumps(sample, indent=2) + "\n")
    variants[farm] = {}
    for acres in (0.5, 3, 10, 50, 100):
        overrides = {}
        for result in sample["recommend"]["crops"]:
            crop = requirements[result["id"]]
            scale = namespace["scale_info"](SimpleNamespace(**crop), acres)
            score, flags = result["score"], result["flags"][:]
            if scale["fit"] == "too_small":
                if score is not None:
                    score = min(score, 40)
                flags = [scale["note"], *flags][:4]
            elif scale["fit"] == "small":
                flags = [*flags[:3], scale["note"]]
            overrides[result["id"]] = {
                "scale": scale, "score": score, "flags": flags,
                "est_gross_value": namespace["estimated_gross_value"](result["avg_yield"], result["price"], acres),
            }
        variants[farm][str(acres)] = overrides
(MOCKS / "acreage.json").write_text(json.dumps(variants, indent=2) + "\n")
