"""Small JSON file cache in backend/data/cache so each source is fetched once."""

import hashlib
import json
from pathlib import Path
from typing import Any

from app.config import CACHE_DIR


def cache_path(namespace: str, params: dict[str, Any]) -> Path:
    """Build a stable file path from a namespace and request params."""
    canonical = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return CACHE_DIR / namespace / f"{digest}.json"


def read_cache(namespace: str, params: dict[str, Any]) -> Any | None:
    """Return cached data, or None if there is no cache entry."""
    path = cache_path(namespace, params)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def write_cache(namespace: str, params: dict[str, Any], data: Any) -> None:
    """Store data for these params."""
    path = cache_path(namespace, params)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
