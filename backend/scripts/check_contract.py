"""Check live API responses against docs/api-contract.md.

Start the server first (uvicorn app.main:app), then from backend/:
    python -m scripts.check_contract [base_url]

For each demo farm it fetches /api/recommend and /api/crops/<top crop>, checks
field names, types, units, ordering and rounding, and prints a PASS/FAIL
table. Exit code 1 if any check fails.
"""

import sys
from typing import Any

import httpx

from app.config import DEMO_FARMS

NUM = (int, float)
OPT_NUM = (int, float, type(None))
OPT_STR = (str, type(None))
FACTORS = ("soil_ph", "drainage", "season_temp", "frost_risk", "rainfall", "local_history")
FACTOR_UNITS = {"soil_ph": "pH", "season_temp": "C avg", "frost_risk": "freeze days in season",
                "rainfall": "mm in season"}  # drainage and local_history have no unit

LOCATION = {"lat": NUM, "lon": NUM, "county": OPT_STR, "county_fips": OPT_STR, "state": (str,)}
CONDITIONS = {
    "soil_ph": OPT_NUM, "organic_matter_pct": OPT_NUM, "sand_pct": OPT_NUM, "clay_pct": OPT_NUM,
    "texture": OPT_STR, "drainage": OPT_STR, "annual_precip_mm": OPT_NUM, "frost_free_days": OPT_NUM,
    "last_spring_frost": OPT_STR, "first_fall_frost": OPT_STR, "avg_summer_high_c": OPT_NUM,
    "avg_winter_low_c": OPT_NUM,
}
CROP = {"id": (str,), "name": (str,), "score": (int, type(None)), "season_label": (str,), "factors": (dict,),
        "factor_details": (dict,), "avg_yield": (dict, type(None)), "price": (dict, type(None)),
        "limited_by": (list,), "flags": (list,)}
SCORING = {"weights": (dict,), "critical_factors": (list,), "critical_threshold": (int,), "critical_cap": (int,)}
RECOMMEND = {"location": (dict,), "conditions": (dict,), "crops": (list,), "warnings": (list,),
             "scoring": (dict,)}
DETAIL = {**CROP, "requirements": (dict,), "general_guidance": (str,), "extension_links": (list,),
          "conditions": (dict,), "location": (dict,), "scoring": (dict,)}


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, bool, str]] = []

    def check(self, where: str, name: str, ok: bool, why: str = "") -> None:
        self.rows.append((where, name, ok, "" if ok else why))

    def print(self) -> bool:
        width = max(len(f"{w} | {n}") for w, n, _, _ in self.rows)
        for where, name, ok, why in self.rows:
            print(f"{f'{where} | {name}':<{width}} | {'PASS' if ok else 'FAIL'}{'  ' + why if why else ''}")
        failed = sum(not ok for _, _, ok, _ in self.rows)
        print(f"\n{len(self.rows) - failed} passed, {failed} failed")
        return failed == 0


def shape_errors(obj: Any, spec: dict[str, tuple[type, ...]], path: str) -> list[str]:
    """Exact keys and types; bool is rejected where a number is expected."""
    if not isinstance(obj, dict):
        return [f"{path} is {type(obj).__name__}, not object"]
    errors = [f"{path}: missing {key}" for key in spec if key not in obj]
    errors += [f"{path}: extra {key}" for key in obj if key not in spec]
    for key, types in spec.items():
        value = obj.get(key)
        if key in obj and (not isinstance(value, types) or isinstance(value, bool)):
            errors.append(f"{path}.{key} is {type(value).__name__}")
    return errors


def decimals(value: float) -> int:
    text = repr(float(value))
    return 0 if "e" in text else len(text.split(".")[1].rstrip("0"))


def rounding_errors(obj: Any, path: str, places: int) -> list[str]:
    """Every float under obj has at most `places` decimals."""
    if isinstance(obj, dict):
        return [e for key, value in obj.items() for e in rounding_errors(value, f"{path}.{key}", places)]
    if isinstance(obj, list):
        return [e for i, value in enumerate(obj) for e in rounding_errors(value, f"{path}[{i}]", places)]
    if isinstance(obj, float) and decimals(obj) > places:
        return [f"{path}={obj}"]
    return []


def check_crop(report: Report, where: str, crop: dict[str, Any], spec: dict[str, tuple[type, ...]]) -> None:
    errors = shape_errors(crop, spec, crop.get("id", "crop"))
    report.check(where, f"{crop.get('id')}: field names and types", not errors, "; ".join(errors[:3]))
    factors, details = crop.get("factors") or {}, crop.get("factor_details") or {}
    report.check(where, f"{crop.get('id')}: factor keys", tuple(factors) == FACTORS and tuple(details) == FACTORS,
                 f"{list(factors)} / {list(details)}")
    bad = [k for k, v in factors.items() if v is not None and (not isinstance(v, int) or not 0 <= v <= 100)]
    report.check(where, f"{crop.get('id')}: factor scores int 0-100", not bad, str(bad))
    unit_errors = []
    for key, detail in details.items():
        expected = {"value", "ideal", "unit"} if key in FACTOR_UNITS else {"value", "ideal"}
        if set(detail) != expected:
            unit_errors.append(f"{key} keys {sorted(detail)}")
        elif key in FACTOR_UNITS and detail["unit"] != FACTOR_UNITS[key]:
            unit_errors.append(f"{key} unit {detail['unit']!r}")
    if crop.get("avg_yield"):
        y = crop["avg_yield"]
        if set(y) != {"value", "unit", "level"} or "/ ACRE" not in (y["unit"] or "") \
                or y["level"] not in ("county", "state"):
            unit_errors.append(f"avg_yield {y}")
    if crop.get("price"):
        p = crop["price"]
        if set(p) != {"low", "high", "unit"} or not (p["unit"] or "").startswith("$ / ") or p["low"] > p["high"]:
            unit_errors.append(f"price {p}")
    report.check(where, f"{crop.get('id')}: units", not unit_errors, "; ".join(unit_errors[:3]))
    # Coordinates echo the request and weights are exact; conditions are checked separately.
    skip = ("price", "requirements", "location", "scoring", "conditions")
    round_errors = rounding_errors({k: v for k, v in crop.items() if k not in skip}, crop.get("id", ""), 1)
    round_errors += rounding_errors(crop.get("price"), f"{crop.get('id')}.price", 2)
    report.check(where, f"{crop.get('id')}: rounding (1 dp, prices 2 dp)", not round_errors,
                 "; ".join(round_errors[:3]))


def check_common(report: Report, where: str, body: dict[str, Any]) -> None:
    for name, spec in (("location", LOCATION), ("conditions", CONDITIONS), ("scoring", SCORING)):
        errors = shape_errors(body.get(name), spec, name)
        report.check(where, f"{name}: field names and types", not errors, "; ".join(errors[:3]))
    report.check(where, "conditions: rounding (1 dp)", not rounding_errors(body.get("conditions"), "conditions", 1),
                 "; ".join(rounding_errors(body.get("conditions"), "conditions", 1)[:3]))
    scoring = body.get("scoring") or {}
    report.check(where, "scoring: weights cover factors and sum to 1",
                 tuple(scoring.get("weights", {})) == FACTORS
                 and abs(sum(scoring.get("weights", {}).values()) - 1) < 1e-9, str(scoring.get("weights")))


def main(base_url: str) -> bool:
    report = Report()
    with httpx.Client(base_url=base_url, timeout=180) as client:
        for farm, (lat, lon) in DEMO_FARMS.items():
            response = client.get("/api/recommend", params={"lat": lat, "lon": lon})
            report.check(farm, "recommend: HTTP 200", response.status_code == 200, str(response.status_code))
            if response.status_code != 200:
                continue
            body = response.json()
            errors = shape_errors(body, RECOMMEND, "recommend")
            report.check(farm, "recommend: top-level fields", not errors, "; ".join(errors))
            check_common(report, farm, body)
            crops = body["crops"]
            report.check(farm, "recommend: 13 crops, unique ids", len({c["id"] for c in crops}) == 13 == len(crops))
            keys = [(-(c["score"] if c["score"] is not None else -1), c["name"]) for c in crops]
            report.check(farm, "recommend: sorted by score desc, then name", keys == sorted(keys))
            for crop in crops:
                check_crop(report, farm, crop, CROP)
            report.check(farm, "recommend: warnings are strings", all(isinstance(w, str) for w in body["warnings"]))

            top = crops[0]["id"]
            detail_response = client.get(f"/api/crops/{top}", params={"lat": lat, "lon": lon})
            report.check(farm, f"detail {top}: HTTP 200", detail_response.status_code == 200)
            if detail_response.status_code != 200:
                continue
            detail = detail_response.json()
            check_crop(report, farm, detail, DETAIL)
            check_common(report, farm, detail)
            links = detail["extension_links"]
            report.check(farm, f"detail {top}: extension links", bool(links) and all(
                set(link) == {"title", "url"} and link["url"].startswith("https://") for link in links))
            same = {k: detail[k] for k in CROP} == next(c for c in crops if c["id"] == top)
            report.check(farm, f"detail {top}: matches its recommend entry", same)
            report.check(farm, f"detail {top}: no guidance or links in requirements",
                         not {"general_guidance", "extension_links"} & set(detail["requirements"]))
    return report.print()


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000") else 1)
