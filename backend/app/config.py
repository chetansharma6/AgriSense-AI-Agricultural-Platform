"""App settings, loaded once from environment variables and backend/.env."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"

load_dotenv(BACKEND_DIR / ".env")

NASS_API_KEY = os.getenv("NASS_API_KEY", "").strip()

# DEMO_MODE=true serves only cached data and never calls an outside API, so
# the demo cannot be slowed or broken by a network or service problem.
DEMO_MODE = os.getenv("DEMO_MODE", "false").strip().lower() in {"1", "true", "yes"}

# Comma-separated browser origins allowed to call the API. In Codespaces, add
# the forwarded frontend URL (https://<name>-3000.app.github.dev).
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
# Vercel deployments (production and preview URLs).
CORS_ORIGIN_REGEX = r"https://.*\.vercel\.app"

FL_BBOX = (24.3, 31.1, -87.7, -79.9)  # lat_min, lat_max, lon_min, lon_max


def in_florida(lat: float, lon: float) -> bool:
    """Return True if the point is inside the Florida bounding box."""
    lat_min, lat_max, lon_min, lon_max = FL_BBOX
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def nass_api_key() -> str:
    """Return the NASS Quick Stats key. Raises if it is not configured."""
    if not NASS_API_KEY:
        raise RuntimeError("NASS_API_KEY is not set (add it to backend/.env)")
    return NASS_API_KEY
