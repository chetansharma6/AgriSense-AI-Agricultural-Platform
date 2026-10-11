"""Crop requirements table, loaded from backend/data/crops.json."""

import json
import math
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, model_validator

from app.config import DATA_DIR

# SSURGO drainage classes, driest to wettest.
DRAINAGE_CLASSES = [
    "Excessively drained",
    "Somewhat excessively drained",
    "Well drained",
    "Moderately well drained",
    "Somewhat poorly drained",
    "Poorly drained",
    "Very poorly drained",
]


class NassSeries(BaseModel):
    acres_descs: list[str]  # county Census acreage series, any of which counts
    yield_desc: str
    price_desc: str


class GrowingWindow(BaseModel):
    label: str
    start: str  # MM-DD
    end: str  # MM-DD, may be earlier than start (window crosses New Year)
    months: list[int]  # calendar months the crop is in the field

    @model_validator(mode="after")
    def _check_dates(self) -> "GrowingWindow":
        for month_day in (self.start, self.end):
            month, _, day = month_day.partition("-")
            if not (month.isdigit() and day.isdigit() and 1 <= int(month) <= 12 and 1 <= int(day) <= 31):
                raise ValueError(f"{self.label}: bad MM-DD date {month_day!r}")
        if not self.months or any(not 1 <= m <= 12 for m in self.months):
            raise ValueError(f"{self.label}: months must be 1-12")
        return self


class ExtensionLink(BaseModel):
    title: str
    url: str

    @model_validator(mode="after")
    def _https_url(self) -> "ExtensionLink":
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("source URL must be an absolute HTTPS URL")
        return self


class CropEvidence(BaseModel):
    """Audit metadata retained in crop data, not exposed in recommendation output."""

    nutrient_status: str  # verified, conditional, or planning_assumption
    nitrogen_recommendation_type: str  # fixed, range, conditional, or zero_n
    nitrogen_note: str
    source_verified: bool
    recommended_range_lb_per_acre: tuple[float, float] | None = None

    @model_validator(mode="after")
    def _evidence_is_consistent(self) -> "CropEvidence":
        if self.nutrient_status not in {"verified", "conditional", "planning_assumption"}:
            raise ValueError("unknown nutrient evidence status")
        if self.nitrogen_recommendation_type not in {"fixed", "range", "conditional", "zero_n"}:
            raise ValueError("unknown nitrogen recommendation type")
        if not self.nitrogen_note.strip():
            raise ValueError("nitrogen evidence note is required")
        if self.nitrogen_recommendation_type in {"range", "conditional"} and self.recommended_range_lb_per_acre is None:
            raise ValueError("conditional nitrogen evidence needs a range")
        if self.recommended_range_lb_per_acre is not None:
            low, high = self.recommended_range_lb_per_acre
            if not (math.isfinite(low) and math.isfinite(high) and 0 <= low <= high):
                raise ValueError("nitrogen range must be finite and non-negative")
        return self


class Crop(BaseModel):
    """One crop's Florida requirements. Ranges are trapezoids: 100 inside the
    ideal band, falling linearly to 0 at the hard limit."""

    id: str
    name: str
    nass_commodity: str
    nass_class: str | None
    nass: NassSeries
    fl_windows: list[GrowingWindow]
    ph_min: float
    ph_ideal_min: float
    ph_ideal_max: float
    ph_max: float
    drainage: tuple[str, str]  # driest and wettest ideal classes
    muck_suitable: bool
    temp_min_c: float  # season mean temperature
    temp_ideal_min_c: float
    temp_ideal_max_c: float
    temp_max_c: float
    max_freeze_days: float
    rain_mm_per_month: tuple[float, float]
    general_guidance: str
    extension_links: list[ExtensionLink]
    source_notes: str
    needs_review: bool
    min_practical_acres: float
    small_acres: float
    scale_note: str
    n_lb_per_acre: float | None
    nutrient_source: ExtensionLink
    evidence: CropEvidence

    @model_validator(mode="after")
    def _check_ranges(self) -> "Crop":
        """Every trapezoid needs hard_min < ideal_min <= ideal_max < hard_max, or scoring divides by zero."""
        for name in ("ph", "temp"):
            suffix = "_c" if name == "temp" else ""
            limits = [getattr(self, f"{name}_{part}{suffix}") for part in ("min", "ideal_min", "ideal_max", "max")]
            if not limits[0] < limits[1] <= limits[2] < limits[3]:
                raise ValueError(f"{self.id}: {name} limits must satisfy min < ideal_min <= ideal_max < max, got {limits}")
        low, high = self.rain_mm_per_month
        if not 0 < low <= high:
            raise ValueError(f"{self.id}: rain_mm_per_month must satisfy 0 < low <= high, got {[low, high]}")
        for drainage_class in self.drainage:
            if drainage_class not in DRAINAGE_CLASSES:
                raise ValueError(f"{self.id}: unknown drainage class {drainage_class!r}")
        if DRAINAGE_CLASSES.index(self.drainage[0]) > DRAINAGE_CLASSES.index(self.drainage[1]):
            raise ValueError(f"{self.id}: drainage must list the driest class first")
        if self.max_freeze_days < 0:
            raise ValueError(f"{self.id}: max_freeze_days must be >= 0")
        if not 0 < self.small_acres <= self.min_practical_acres:
            raise ValueError(f"{self.id}: small_acres must be positive and <= min_practical_acres")
        if self.n_lb_per_acre is not None and (not math.isfinite(self.n_lb_per_acre) or self.n_lb_per_acre < 0):
            raise ValueError(f"{self.id}: n_lb_per_acre must be finite and >= 0")
        nutrient_host = urlparse(self.nutrient_source.url).hostname
        if nutrient_host not in {"edis.ifas.ufl.edu", "ask.ifas.ufl.edu"}:
            raise ValueError(f"{self.id}: nutrient source must be a UF/IFAS URL")
        yield_unit = self.nass.yield_desc.rsplit("MEASURED IN ", 1)[-1].removesuffix(" / ACRE").upper().rstrip("S")
        price_unit = self.nass.price_desc.rsplit("MEASURED IN $ / ", 1)[-1].upper().rstrip("S")
        if not yield_unit or yield_unit != price_unit:
            raise ValueError(f"{self.id}: yield and price units are incompatible")
        if not self.fl_windows:
            raise ValueError(f"{self.id}: needs at least one Florida growing window")
        return self

    def requirements(self) -> dict[str, Any]:
        """Raw requirement fields (everything except guidance and links)."""
        return self.model_dump(exclude={"general_guidance", "extension_links", "evidence"})


@lru_cache(maxsize=1)
def load_crops() -> dict[str, Crop]:
    """Return all crops keyed by id, in file order."""
    raw = json.loads((DATA_DIR / "crops.json").read_text())
    crops = [Crop.model_validate(item) for item in raw]
    return {crop.id: crop for crop in crops}


def get_crop(crop_id: str) -> Crop | None:
    """One crop by id, or None if unknown."""
    return load_crops().get(crop_id)
