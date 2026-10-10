"""App settings, loaded once from environment variables and backend/.env."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"

load_dotenv(BACKEND_DIR / ".env")

# Comma-separated browser origins allowed to call the API. In Codespaces, add
# the forwarded frontend URL (https://<name>-3000.app.github.dev).
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

FL_LAT_MIN, FL_LAT_MAX = 24.3, 31.1
FL_LON_MIN, FL_LON_MAX = -87.7, -79.9


def in_florida(lat: float, lon: float) -> bool:
    """Return True if the point is inside the Florida bounding box."""
    return FL_LAT_MIN <= lat <= FL_LAT_MAX and FL_LON_MIN <= lon <= FL_LON_MAX


@lru_cache(maxsize=1)
def nass_api_key() -> str:
    """Return the NASS Quick Stats key. Raises if it is not configured."""
    key = os.getenv("NASS_API_KEY", "").strip()
    if not key:
        raise RuntimeError("NASS_API_KEY is not set (add it to backend/.env)")
    return key
