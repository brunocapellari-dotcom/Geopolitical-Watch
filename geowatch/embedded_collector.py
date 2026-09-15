from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

from .pipeline import run

_LOCK = threading.RLock()
_RUN_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
_STATE: dict[str, object] = {
    "enabled": False,
    "running": False,
    "last_started_at": None,
    "last_finished_at": None,
    "last_status": None,
    "last_error": None,
    "last_result": None,
    "run_count": 0,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def enabled() -> bool:
    return os.environ.get("GEOWATCH_EMBEDDED_COLLECTOR", "").strip().casefold() in {"1", "true", "yes", "on"}


def interval_seconds() -> int:
    raw = os.environ.get("GEOWATCH_COLLECT_INTERVAL_SECONDS", "3600")
    try:
        value = int(raw)
    except ValueError:
        value = 3600
    return max(900, min(value, 86400))


def config_path() -> str:
    explicit = os.environ.get("GEOWATCH_COLLECT_CONFIG", "").strip()
    if explicit:
        return explicit
    if os.environ.get("REPLIT_DEPLOYMENT") == "1" or os.environ.get("GEOWATCH_STRICT_PRODUCTION", "").strip().casefold() in {"1", "true", "yes", "on"}:
        return "config/sources.production.json"
    return "config/sources.public-beta.json"


def status() -> dict:
    with _LOCK:
        return {
            "schema_version": "geowatch-embedded-collector-status-v1",
            **_STATE,
            "enabled": enabled(),
            "interval_seconds": interval_seconds(),
            "config_path": config_path(),
        }


def ensure_started() -> bool:
    global _THREAD
    if not enabled():
        with _LOCK:
            _STATE["enabled"] = False
        return False
    with _LOCK:
        _STATE["enabled"] = True
        if _THREAD and _THREAD.is_alive():
            return True
        _THREAD = threading.Thread(target=_loop, name="geowatch-collector", daemon=True)
        _THREAD.start()
        return True


def run_once() -> dict:
    if not _RUN_LOCK.acquire(blocking=False):
        return {"status": "skipped", "reason": "collector run already in progress"}
    try:
        started = _utc_now()
        with _LOCK:
            _STATE.update({"running": True, "last_started_at": started, "last_error": None})
        config = config_path()
        raw_root = os.environ.get("GEOWATCH_RAW_ROOT", "data/raw")
        reports_root = os.environ.get("GEOWATCH_REPORTS_ROOT", "reports")
        result = run(config_path=config, db_path=None, raw_root=raw_root, reports_root=reports_root)
        finished = _utc_now()
        with _LOCK:
            _STATE.update({
                "running": False,
                "last_finished_at": finished,
                "last_status": "ok",
                "last_result": result,
                "run_count": int(_STATE.get("run_count") or 0) + 1,
            })
        return {"status": "ok", "result": result}
    except Exception as exc:
        finished = _utc_now()
        with _LOCK:
            _STATE.update({
                "running": False,
                "last_finished_at": finished,
                "last_status": "error",
                "last_error": f"{type(exc).__name__}: {exc}",
                "run_count": int(_STATE.get("run_count") or 0) + 1,
            })
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        _RUN_LOCK.release()


def _loop() -> None:
    while enabled():
        started = time.monotonic()
        run_once()
        elapsed = time.monotonic() - started
        sleep_for = max(30.0, interval_seconds() - elapsed)
        time.sleep(sleep_for)
    with _LOCK:
        _STATE["running"] = False


def reset_for_tests() -> None:
    global _THREAD
    with _LOCK:
        _STATE.update({
            "enabled": False,
            "running": False,
            "last_started_at": None,
            "last_finished_at": None,
            "last_status": None,
            "last_error": None,
            "last_result": None,
            "run_count": 0,
        })
        _THREAD = None
