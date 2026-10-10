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
from pathlib import Path
from typing import Any

from app.config import CACHE_DIR

log = logging.getLogger(__name__)


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
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as error:  # unreadable or corrupt: fetch again
        log.warning("cache read failed for %s: %s", path.relative_to(CACHE_DIR.parent), error)
        return None


def write_cache(namespace: str, params: dict[str, Any], data: Any) -> None:
    """Store data for these params. Writes to a temp file and renames it into
    place so a concurrent reader never sees a half-written file."""
    path = cache_path(namespace, params)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    except OSError as error:  # read-only or full disk: serve without caching
        log.warning("cache write skipped for %s: %s", namespace, error)
        return
    try:
        with os.fdopen(fd, "w") as tmp:
            json.dump(data, tmp)
        os.replace(tmp_name, path)
    except OSError as error:  # disk filled up mid-write: drop the partial file, keep serving
        _remove(tmp_name)
        log.warning("cache write skipped for %s: %s", namespace, error)
    except BaseException:
        _remove(tmp_name)
        raise


def _remove(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass
