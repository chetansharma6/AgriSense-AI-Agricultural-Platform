"""AgriSense FastAPI app."""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGIN_REGEX, CORS_ORIGINS, in_florida
from app.crops import load_crops
from app.schemas import CropDetail, RecommendResponse
from app.service import OutsideFlorida, crop_detail, recommend

# Per-source timings from app.service show up next to uvicorn's access log.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")

app = FastAPI(title="AgriSense API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_methods=["GET"],
    allow_headers=["*"],
)

NOT_IN_FLORIDA = "Location must be in Florida"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# exclude_unset: optional keys the service never set (e.g. "unit" on drainage) stay absent, as in the contract.
@app.get("/api/recommend", response_model=RecommendResponse, response_model_exclude_unset=True)
def get_recommend(lat: float = Query(...), lon: float = Query(...)) -> dict[str, Any]:
    _require_florida(lat, lon)
    try:
        return recommend(lat, lon)
    except OutsideFlorida:
        raise HTTPException(status_code=400, detail=NOT_IN_FLORIDA) from None


@app.get("/api/crops/{crop_id}", response_model=CropDetail, response_model_exclude_unset=True)
def get_crop(crop_id: str, lat: float = Query(...), lon: float = Query(...)) -> dict[str, Any]:
    if crop_id not in load_crops():
        raise HTTPException(status_code=404, detail="Unknown crop")
    _require_florida(lat, lon)
    try:
        detail = crop_detail(crop_id, lat, lon)
    except OutsideFlorida:
        raise HTTPException(status_code=400, detail=NOT_IN_FLORIDA) from None
    assert detail is not None
    return detail


def _require_florida(lat: float, lon: float) -> None:
    if not in_florida(lat, lon):
        raise HTTPException(status_code=400, detail=NOT_IN_FLORIDA)
