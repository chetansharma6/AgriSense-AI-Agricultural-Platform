"""Response models for docs/api-contract.md.

FastAPI validates every response against these, so a field added, renamed or
mistyped in the service fails loudly (in tests) instead of reaching the
frontend. Optional fields are the ones the contract allows to be null.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Location(Strict):
    lat: float
    lon: float
    county: str | None
    county_fips: str | None
    state: str


class Conditions(Strict):
    soil_ph: float | None
    organic_matter_pct: float | None
    sand_pct: float | None
    clay_pct: float | None
    texture: str | None
    drainage: str | None
    annual_precip_mm: float | None
    frost_free_days: float | None  # average over years, so fractional
    last_spring_frost: str | None  # MM-DD
    first_fall_frost: str | None  # MM-DD
    avg_summer_high_c: float | None
    avg_winter_low_c: float | None


class FactorDetail(Strict):
    value: int | float | str | None
    ideal: str | None
    unit: str | None = None


class Factors(Strict):
    soil_ph: int | None
    drainage: int | None
    season_temp: int | None
    frost_risk: int | None
    rainfall: int | None
    local_history: int | None


class FactorDetails(Strict):
    soil_ph: FactorDetail
    drainage: FactorDetail
    season_temp: FactorDetail
    frost_risk: FactorDetail
    rainfall: FactorDetail
    local_history: FactorDetail


class YieldInfo(Strict):
    value: float | None
    unit: str | None
    level: str | None


class PriceRange(Strict):
    low: float | None
    high: float | None
    unit: str | None


class ExtensionLink(Strict):
    title: str
    url: str


class Scale(Strict):
    fit: str | None
    min_practical_acres: float
    note: str | None


class GrossValue(Strict):
    low: float
    high: float
    label: str


class NutrientPlan(Strict):
    n_lb_per_acre: float | None
    soil_test_first: bool
    lime_note: str | None
    practices: list[str]
    sources: list[ExtensionLink]


class ActionPlan(Strict):
    check_before_planting: str
    first_test: str
    planting_window: str
    major_risk: str
    uf_ifas_follow_up: ExtensionLink


class ScoringRules(Strict):
    weights: dict[str, float]
    critical_factors: list[str]
    critical_threshold: int
    critical_cap: int


class SourceStatus(Strict):
    name: str
    status: str
    detail: str | None = None
    url: str = ""
    data_period: str = ""
    data_status: str = "live"
    geographic_level: str = ""
    limitations: list[str] = []


class FawnStation(Strict):
    name: str
    distance_km: float


class Provenance(Strict):
    mode: str
    sources: list[SourceStatus]
    fawn_station: FawnStation | None = None


class Confidence(Strict):
    level: str
    available_factors: int
    total_factors: int
    available_factor_names: list[str]
    missing_factor_names: list[str]
    data_status: str
    county_history_status: str
    partial: bool
    notes: list[str]


class CropResult(Strict):
    id: str
    name: str
    score: int | None
    season_label: str
    factors: Factors
    factor_details: FactorDetails
    avg_yield: YieldInfo | None
    price: PriceRange | None
    scale: Scale
    est_gross_value: GrossValue | None
    limited_by: list[str]
    flags: list[str]
    action_plan: ActionPlan
    risk_notes: list[str]


class RecommendResponse(Strict):
    location: Location
    conditions: Conditions
    crops: list[CropResult]
    warnings: list[str]
    scoring: ScoringRules
    provenance: Provenance | None = None
    confidence: Confidence | None = None


class CropDetail(CropResult):
    requirements: dict[str, Any]
    general_guidance: str
    extension_links: list[ExtensionLink]
    nutrient_plan: NutrientPlan
    conditions: Conditions
    location: Location
    scoring: ScoringRules
    provenance: Provenance | None = None
    confidence: Confidence | None = None
