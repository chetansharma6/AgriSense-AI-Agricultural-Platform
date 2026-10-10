"""USDA NRCS Soil Data Access (SSURGO): soil properties for the top 30 cm.

Two queries per point: the map unit key (mukey) under the point, then every
component and horizon of that map unit. Horizon values are depth-weighted
over 0-30 cm within each component, then components are weighted by their
share of the map unit (comppct_r).

Run `python -m app.clients.soil` from backend/ to print the demo farms.
"""

from typing import Any, TypedDict

import httpx

from app.cache import read_cache, write_cache
from app.clients.http import http

SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
SOURCE = "USDA NRCS SSURGO"
TOP_DEPTH_CM = 30.0
PROPERTIES = {  # output key -> SSURGO horizon column
    "soil_ph": "ph1to1h2o_r",
    "organic_matter_pct": "om_r",
    "sand_pct": "sandtotal_r",
    "clay_pct": "claytotal_r",
}

_MUKEY_SQL = "SELECT mukey FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('point({lon:.6f} {lat:.6f})')"
_HORIZON_SQL = """
SELECT c.cokey, c.compname, c.comppct_r, c.drainagecl, c.majcompflag,
       ch.hzdept_r, ch.hzdepb_r, ch.ph1to1h2o_r, ch.om_r,
       ch.sandtotal_r, ch.claytotal_r
FROM component c
LEFT JOIN chorizon ch ON ch.cokey = c.cokey
WHERE c.mukey = '{mukey}'
"""


class SoilNotFound(Exception):
    """No soil map unit at the point (water, or an unmapped urban area)."""


class SoilServiceDown(RuntimeError):
    """SDA answered with a web page instead of JSON (it has a daily
    maintenance window, 12:30-12:45 AM US Central)."""


class Soil(TypedDict):
    soil_ph: float | None
    organic_matter_pct: float | None
    sand_pct: float | None
    clay_pct: float | None
    texture: str | None
    drainage: str | None
    mukey: str
    dominant_component: str | None
    source: str


def sda_query(sql: str) -> list[dict[str, str | None]]:
    """Run SQL on Soil Data Access and return rows as dicts of strings.
    Retries once on a timeout or a 5xx response."""
    for attempt in (1, 2):
        try:
            response = http().post(SDA_URL, json={"query": sql, "format": "JSON+COLUMNNAME"})
        except httpx.TimeoutException:
            if attempt == 2:
                raise
            continue
        if response.status_code >= 500 and attempt == 1:
            continue
        response.raise_for_status()
        if response.text.lstrip().startswith("<"):
            raise SoilServiceDown(response.text[:200])
        return parse_table(response.json())
    raise AssertionError("unreachable")


def parse_table(payload: dict[str, Any]) -> list[dict[str, str | None]]:
    """JSON+COLUMNNAME: the first row of "Table" is column names, the rest data."""
    table = payload.get("Table") or []
    if len(table) < 2:
        return []
    columns = table[0]
    return [dict(zip(columns, row)) for row in table[1:]]


def get_mukey(lat: float, lon: float) -> str:
    """Map unit key under the point. WKT puts longitude first."""
    rows = sda_query(_MUKEY_SQL.format(lat=lat, lon=lon))
    if not rows:
        raise SoilNotFound("No soil map unit at this point (water or urban area?)")
    return str(rows[0]["mukey"])


def get_soil(lat: float, lon: float) -> Soil:
    """Top-30-cm soil properties at a point. Raises SoilNotFound."""
    params = {"lat": round(lat, 4), "lon": round(lon, 4)}
    cached = read_cache("soil", params)
    if cached:
        return cached

    # SoilNotFound is not cached, so a point is never stuck as "no soil".
    mukey = get_mukey(params["lat"], params["lon"])
    rows = [_to_numbers(row) for row in sda_query(_HORIZON_SQL.format(mukey=mukey))]
    soil = summarize_soil(rows, mukey)
    write_cache("soil", params, soil)
    return soil


def summarize_soil(rows: list[dict[str, Any]], mukey: str) -> Soil:
    """Build the soil dict from numeric component/horizon rows."""
    components = component_values(rows)
    values = {key: combine_components(components, key) for key in PROPERTIES}
    ranked = sorted(components, key=lambda c: c["comppct_r"] or 0, reverse=True)
    drainage = next((c["drainagecl"] for c in ranked if c["drainagecl"]), None)
    return {
        **{key: _round(value) for key, value in values.items()},  # type: ignore[typeddict-item]
        "texture": texture_class(values["sand_pct"], values["clay_pct"], values["organic_matter_pct"]),
        "drainage": drainage,
        "mukey": mukey,
        "dominant_component": ranked[0]["compname"] if ranked else None,
        "source": SOURCE,
    }


def component_values(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One entry per component: its fields plus the 0-30 cm depth-weighted
    mean of each property (None if no horizon in range has a value)."""
    horizons_by_component: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        horizons_by_component.setdefault(row["cokey"], []).append(row)

    components = []
    for horizons in horizons_by_component.values():
        first = horizons[0]
        component = {field: first[field] for field in ("cokey", "compname", "comppct_r", "drainagecl")}
        for key, column in PROPERTIES.items():
            component[key] = top_layer_mean(horizons, column)
        components.append(component)
    return components


def top_layer_mean(horizons: list[dict[str, Any]], column: str) -> float | None:
    """Mean of column over 0-30 cm, each horizon weighted by its thickness
    inside that range. A horizon from 25 to 60 cm counts for 5 cm."""
    weighted_sum = total_weight = 0.0
    for horizon in horizons:
        top, bottom, value = horizon["hzdept_r"], horizon["hzdepb_r"], horizon[column]
        if top is None or bottom is None or value is None or top >= TOP_DEPTH_CM:
            continue
        weight = min(bottom, TOP_DEPTH_CM) - top
        if weight > 0:
            weighted_sum += weight * value
            total_weight += weight
    return weighted_sum / total_weight if total_weight else None


def combine_components(components: list[dict[str, Any]], key: str) -> float | None:
    """Mean across components weighted by comppct_r, skipping components
    with no value (the remaining weights are renormalized)."""
    present = [(c["comppct_r"], c[key]) for c in components if c[key] is not None and c["comppct_r"]]
    total = sum(weight for weight, _ in present)
    return sum(weight * value for weight, value in present) / total if total else None


def texture_class(sand: float | None, clay: float | None, om: float | None = None) -> str | None:
    """Simplified texture class for scoring and display."""
    # Organic matter above 20% is organic soil: the Everglades Agricultural
    # Area muck (AGENTS.md: "organic matter > 20% means texture muck").
    if om is not None and om > 20:
        return "muck"
    if sand is None or clay is None:
        return None
    # 85%+ sand: Florida's deep sands (Ridge, flatwoods), very low water holding.
    if sand >= 85:
        return "sand"
    # 70-85% sand: loamy sands, still droughty but hold a little more water.
    if sand >= 70:
        return "loamy sand"
    # Majority sand with under 20% clay: sandy loams, good for most row crops.
    if sand >= 50 and clay < 20:
        return "sandy loam"
    # 35%+ clay: heavy clay soils, slow drainage.
    if clay >= 35:
        return "clay"
    # 27-35% clay: clay loams, fertile but can stay wet.
    if clay >= 27:
        return "clay loam"
    # Everything else is a medium-textured loam.
    return "loam"


def _to_numbers(row: dict[str, str | None]) -> dict[str, Any]:
    """SDA returns every value as a string; convert numeric columns."""
    numeric = {"comppct_r", "hzdept_r", "hzdepb_r", *PROPERTIES.values()}
    return {key: (float(value) if key in numeric and value not in (None, "") else value)
            for key, value in row.items()}


def _round(value: float | None) -> float | None:
    return round(value, 1) if value is not None else None


if __name__ == "__main__":
    import time

    DEMO_FARMS = {
        "marianna": (30.80, -85.25),
        "hastings": (29.71, -81.50),
        "plant_city": (28.03, -82.15),
        "belle_glade": (26.68, -80.68),
    }
    started = time.perf_counter()
    for name, (lat, lon) in DEMO_FARMS.items():
        soil = get_soil(lat, lon)
        print(f"{name}: mukey {soil['mukey']}")
        print(f"  {soil}")
    print(f"elapsed: {time.perf_counter() - started:.2f} s")
