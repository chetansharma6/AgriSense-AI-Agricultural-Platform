"""Crop requirements table, loaded from backend/data/crops.json."""

import json
from functools import lru_cache
from typing import Any

from pydantic import BaseModel

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

    def requirements(self) -> dict[str, Any]:
        """Raw requirement fields (everything except guidance and links)."""
        return self.model_dump(exclude={"general_guidance", "extension_links"})


@lru_cache(maxsize=1)
def load_crops() -> dict[str, Crop]:
    """Return all crops keyed by id, in file order."""
    raw = json.loads((DATA_DIR / "crops.json").read_text())
    crops = [Crop.model_validate(item) for item in raw]
    for crop in crops:
        for drainage_class in crop.drainage:
            if drainage_class not in DRAINAGE_CLASSES:
                raise ValueError(f"{crop.id}: unknown drainage class {drainage_class!r}")
    return {crop.id: crop for crop in crops}


def get_crop(crop_id: str) -> Crop | None:
    """One crop by id, or None if unknown."""
    return load_crops().get(crop_id)
