"""Small JSON file cache in backend/data/cache so each source is fetched once.

The cache is an optimisation only: on a read-only or full disk (some hosts),
writes are skipped with a warning and unreadable entries count as misses, so
requests still succeed from live data.
"""

import hashlib
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from app.config import CACHE_DIR

log = logging.getLogger(__name__)
CACHE_VERSION = 1
DEFAULT_MAX_AGE_S = 7 * 24 * 60 * 60

# These limits cover the committed ten-year daily payloads while preventing a
# stream of unique public coordinates from filling a small Render disk.  POWER
# needs the largest byte budget; FAWN stores one daily series per station.
CACHE_LIMITS: dict[str, tuple[int, int]] = {
    "fcc": (512, 2 * 1024 * 1024),
    "soil": (256, 8 * 1024 * 1024),
    "power": (128, 64 * 1024 * 1024),
    "fawn": (64, 16 * 1024 * 1024),
    "nass": (512, 32 * 1024 * 1024),
}


def cache_path(namespace: str, params: dict[str, Any]) -> Path:
    """Build a stable file path from a namespace and request params."""
    canonical = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return CACHE_DIR / namespace / f"{digest}.json"


def _key(namespace: str, params: dict[str, Any]) -> str:
    return hashlib.sha256(f"{namespace}:".encode() + json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()


def read_cache(namespace: str, params: dict[str, Any], validator: Any = None,
               max_age_s: float = DEFAULT_MAX_AGE_S) -> Any | None:
    """Return cached data, or None if there is no cache entry."""
    path = cache_path(namespace, params)
    if not path.exists():
        return None
    try:
        if time.time() - path.stat().st_mtime > max_age_s:
            return None
        payload = json.loads(path.read_text())
        if not isinstance(payload, dict) or payload.get("version") != CACHE_VERSION or payload.get("key") != _key(namespace, params):
            return None
        data = payload.get("data")
        if validator is not None and not validator(data):
            return None
        return data
    except (OSError, ValueError, TypeError) as error:  # unreadable or corrupt: fetch again
        log.warning("cache read failed for %s: %s", path.relative_to(CACHE_DIR.parent), error)
        return None


def write_cache(namespace: str, params: dict[str, Any], data: Any, validator: Any = None) -> None:
    """Store data for these params. Writes to a temp file and renames it into
    place so a concurrent reader never sees a half-written file."""
    if validator is not None and not validator(data):
        log.warning("cache write skipped for %s: data failed validation", namespace)
        return
    path = cache_path(namespace, params)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    except OSError as error:  # read-only or full disk: serve without caching
        log.warning("cache write skipped for %s: %s", namespace, error)
        return
    try:
        with os.fdopen(fd, "w") as tmp:
            json.dump({"version": CACHE_VERSION, "key": _key(namespace, params),
                       "written_at": time.time(), "data": data}, tmp)
        os.replace(tmp_name, path)
        _evict(namespace)
    except (OSError, TypeError, ValueError) as error:  # cache is optional; keep serving on write failure
        _remove(tmp_name)
        log.warning("cache write skipped for %s: %s", namespace, error)
    except BaseException as error:
        _remove(tmp_name)
        log.warning("cache write skipped for %s: %s", namespace, error)


def _remove(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _evict(namespace: str) -> None:
    """Keep each known provider namespace inside its deterministic quota.

    mtime is the cache recency signal because atomic replacement gives a fresh
    timestamp.  Filename breaks ties, so eviction is repeatable in tests.
    """
    limit = CACHE_LIMITS.get(namespace)
    if limit is None:
        return
    max_entries, max_bytes = limit
    try:
        entries = [(path.stat(), path) for path in (CACHE_DIR / namespace).glob("*.json")]
        entries.sort(key=lambda item: (item[0].st_mtime_ns, item[1].name))
        total = sum(stat.st_size for stat, _ in entries)
        while len(entries) > max_entries or total > max_bytes:
            stat, path = entries.pop(0)
            path.unlink()
            total -= stat.st_size
    except OSError as error:
        # Disk caching is never allowed to turn a successful provider response
        # into a failed request.
        log.warning("cache eviction skipped for %s: %s", namespace, error)
