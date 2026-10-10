"""Crop requirements table, loaded from backend/data/crops.json."""

import json
from functools import lru_cache
from typing import Any

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
        if not self.fl_windows:
            raise ValueError(f"{self.id}: needs at least one Florida growing window")
        return self

    def requirements(self) -> dict[str, Any]:
        """Raw requirement fields (everything except guidance and links)."""
        return self.model_dump(exclude={"general_guidance", "extension_links"})


@lru_cache(maxsize=1)
def load_crops() -> dict[str, Crop]:
    """Return all crops keyed by id, in file order."""
    raw = json.loads((DATA_DIR / "crops.json").read_text())
    crops = [Crop.model_validate(item) for item in raw]
    return {crop.id: crop for crop in crops}


def get_crop(crop_id: str) -> Crop | None:
    """One crop by id, or None if unknown."""
    return load_crops().get(crop_id)
