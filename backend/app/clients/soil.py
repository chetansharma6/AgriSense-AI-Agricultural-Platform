"""USDA NRCS Soil Data Access (SSURGO): surface soil at a point.

Uses the dominant soil component of the map unit under the point and its
top horizon.
"""

from typing import Any, TypedDict

from app.cache import read_cache, write_cache
from app.clients.http import http

SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
MUCK_OM_PCT = 20.0

_QUERY = """
SELECT TOP 1 mu.muname, c.compname, c.comppct_r, c.drainagecl,
       ch.ph1to1h2o_r, ch.om_r, ch.sandtotal_r, ch.claytotal_r
FROM mapunit mu
JOIN component c ON c.mukey = mu.mukey
LEFT JOIN chorizon ch ON ch.cokey = c.cokey
WHERE mu.mukey IN (
    SELECT * FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('point({lon} {lat})'))
ORDER BY c.comppct_r DESC, ch.hzdept_r ASC
"""


class Soil(TypedDict):
    soil_ph: float | None
    organic_matter_pct: float | None
    sand_pct: float | None
    clay_pct: float | None
    texture: str | None
    drainage: str | None
    map_unit: str | None


def get_soil(lat: float, lon: float) -> Soil | None:
    """Return surface soil properties, or None if SSURGO has no map unit here."""
    params = {"lat": round(lat, 4), "lon": round(lon, 4)}
    cached = read_cache("soil", params)
    if cached is not None:
        return cached or None

    sql = _QUERY.format(lat=params["lat"], lon=params["lon"])
    response = http().post(SDA_URL, json={"query": sql, "format": "JSON+COLUMNNAME"})
    response.raise_for_status()
    soil = _parse(response.json())
    write_cache("soil", params, soil or {})
    return soil


def _parse(payload: dict[str, Any]) -> Soil | None:
    table = payload.get("Table") or []
    if len(table) < 2:
        return None
    row = dict(zip(table[0], table[1]))
    om = _num(row["om_r"])
    sand = _num(row["sandtotal_r"])
    clay = _num(row["claytotal_r"])
    return {
        "soil_ph": _num(row["ph1to1h2o_r"]),
        "organic_matter_pct": om,
        "sand_pct": sand,
        "clay_pct": clay,
        "texture": texture_class(sand, clay, om),
        "drainage": row["drainagecl"],
        "map_unit": row["muname"],
    }


def _num(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


def texture_class(sand: float | None, clay: float | None, om: float | None = None) -> str | None:
    """USDA texture class from sand and clay percent. Organic matter above
    20% is muck (Everglades Agricultural Area)."""
    if om is not None and om > MUCK_OM_PCT:
        return "muck"
    if sand is None or clay is None:
        return None
    silt = 100 - sand - clay
    if silt + 1.5 * clay < 15:
        return "sand"
    if silt + 2 * clay < 30:
        return "loamy sand"
    if (7 <= clay < 20 and sand > 52) or (clay < 7 and silt < 50):
        return "sandy loam"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52:
        return "loam"
    if silt >= 80 and clay < 12:
        return "silt"
    if (silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12):
        return "silt loam"
    if 20 <= clay < 35 and silt < 28 and sand > 45:
        return "sandy clay loam"
    if 27 <= clay < 40 and 20 < sand <= 45:
        return "clay loam"
    if 27 <= clay < 40 and sand <= 20:
        return "silty clay loam"
    if clay >= 35 and sand > 45:
        return "sandy clay"
    if clay >= 40 and silt >= 40:
        return "silty clay"
    return "clay"
