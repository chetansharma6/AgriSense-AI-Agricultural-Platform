"""App settings, loaded once from environment variables and backend/.env."""

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"

load_dotenv(BACKEND_DIR / ".env")

NASS_API_KEY = os.getenv("NASS_API_KEY", "").strip()

# DEMO_MODE=true puts a deadline on every recommendation so a live demo never
# hangs: if the data sources take longer than DEMO_DEADLINE_S (or one fails),
# a point within DEMO_FALLBACK_KM of a demo farm gets that farm's saved
# response from data/demo, and any other point gets a quick 503.
DEMO_MODE = os.getenv("DEMO_MODE", "false").strip().lower() in {"1", "true", "yes"}
DEMO_DEADLINE_S = 6.0
DEMO_FALLBACK_KM = 25.0

# Comma-separated browser origins allowed to call the API. In Codespaces, add
# the forwarded frontend URL (https://<name>-3000.app.github.dev).
def _explicit_origins(raw: str) -> list[str]:
    origins = []
    for candidate in raw.split(","):
        origin = candidate.strip()
        parsed = urlparse(origin)
        if origin and "*" not in origin and parsed.scheme in {"http", "https"} and parsed.netloc:
            origins.append(origin.rstrip("/"))
    return origins or ["http://localhost:3000"]


CORS_ORIGINS = _explicit_origins(os.getenv("CORS_ORIGINS", "http://localhost:3000"))
# Origins are explicit by design; never broaden production access to every
# deployment on a shared hosting domain such as *.vercel.app.
CORS_ORIGIN_REGEX = None

FL_BBOX = (24.3, 31.1, -87.7, -79.9)  # lat_min, lat_max, lon_min, lon_max
DEMO_FARMS = {  # name -> (lat, lon), as in AGENTS.md
    "marianna": (30.80, -85.25),
    "hastings": (29.71, -81.50),
    "plant_city": (28.03, -82.15),
    "belle_glade": (26.68, -80.68),
}


def in_florida(lat: float, lon: float) -> bool:
    """Return True if the point is inside the Florida bounding box."""
    lat_min, lat_max, lon_min, lon_max = FL_BBOX
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def nass_api_key() -> str:
    """Return the NASS Quick Stats key. Raises if it is not configured."""
    if not NASS_API_KEY:
        raise RuntimeError("NASS_API_KEY is not set (add it to backend/.env)")
    return NASS_API_KEY
