from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

from .wpi import download, select_candidates

_LOCK = threading.RLock()
_CACHE: tuple[float, list[dict], dict] | None = None
_TTL_SECONDS = 24 * 60 * 60


def enabled() -> bool:
    return os.environ.get("GEOWATCH_WPI_RUNTIME", "").strip().casefold() in {"1", "true", "yes", "on"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_runtime_wpi(*, limit: int = 300) -> tuple[list[dict], dict]:
    """Load official NGA WPI candidates at runtime when explicitly enabled.

    Failure is soft: the core infrastructure catalog remains available and the
    status object exposes the WPI failure instead of fabricating coordinates.
    """
    global _CACHE
    if not enabled():
        return [], {"enabled": False, "status": "disabled", "node_count": 0}

    now = time.monotonic()
    with _LOCK:
        if _CACHE and _CACHE[0] > now:
            return [dict(row) for row in _CACHE[1]], {**_CACHE[2], "cache_hit": True}

    try:
        rows, source_url = download()
        nodes = select_candidates(rows, limit=max(1, min(int(limit), 500)), min_per_water_body=3)
        status = {
            "enabled": True,
            "status": "ok",
            "source": "NGA World Port Index",
            "source_url": source_url,
            "source_row_count": len(rows),
            "node_count": len(nodes),
            "loaded_at": _utc_now(),
            "cache_hit": False,
            "structural_context_not_live_status": True,
        }
    except Exception as exc:
        return [], {
            "enabled": True,
            "status": "error",
            "node_count": 0,
            "loaded_at": _utc_now(),
            "error": f"{type(exc).__name__}: {exc}",
            "structural_context_not_live_status": True,
        }

    with _LOCK:
        _CACHE = (time.monotonic() + _TTL_SECONDS, [dict(row) for row in nodes], dict(status))
    return nodes, status


def clear_runtime_wpi_cache() -> None:
    global _CACHE
    with _LOCK:
        _CACHE = None
