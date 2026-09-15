from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

from .source_collection import collect_source_once, load_collection_spec
from .source_registry import load_registry
from .storage_factory import open_store

_LOCK = threading.RLock()
_THREAD: threading.Thread | None = None
_STATE: dict[str, object] = {
    "enabled": False,
    "running": False,
    "last_tick_at": None,
    "last_results": {},
    "tick_count": 0,
}


def enabled() -> bool:
    return os.environ.get("GEOWATCH_SOURCE_SCHEDULER", "").strip().casefold() in {"1", "true", "yes", "on"}


def tick_seconds() -> int:
    try:
        value = int(os.environ.get("GEOWATCH_SOURCE_SCHEDULER_TICK", "30"))
    except ValueError:
        value = 30
    return max(15, min(value, 300))


def status() -> dict[str, object]:
    with _LOCK:
        return {
            "schema_version": "geowatch-source-scheduler-status-v1",
            **_STATE,
            "enabled": enabled(),
            "tick_seconds": tick_seconds(),
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
        _THREAD = threading.Thread(target=_loop, name="geowatch-source-scheduler", daemon=True)
        _THREAD.start()
        return True


def run_tick() -> dict[str, object]:
    registry = load_registry()
    store = open_store()
    try:
        last_success: dict[str, str | None] = {}
        for spec in registry.specs:
            checkpoint = store.get_checkpoint(spec.source_id)
            last_success[spec.source_id] = checkpoint.get("last_success_at") if checkpoint else None
    finally:
        store.close()

    now = datetime.now(timezone.utc)
    due = registry.due_sources(last_success, now=now)
    results: dict[str, object] = {}
    for spec in due:
        # A registry entry can be implemented by a specialized runtime (WPI, AIS,
        # ADS-B) without belonging to the batch collector. Those are not forced
        # through this scheduler.
        if load_collection_spec(spec.source_id) is None:
            results[spec.source_id] = {
                "status": "delegated",
                "runtime_mode": spec.runtime_mode,
                "implementation": spec.implementation,
            }
            continue
        results[spec.source_id] = collect_source_once(spec.source_id)

    with _LOCK:
        _STATE.update({
            "running": False,
            "last_tick_at": now.isoformat(),
            "last_results": results,
            "tick_count": int(_STATE.get("tick_count") or 0) + 1,
        })
    return {"due": [spec.source_id for spec in due], "results": results}


def _loop() -> None:
    while enabled():
        started = time.monotonic()
        with _LOCK:
            _STATE["running"] = True
        try:
            run_tick()
        except Exception as exc:
            with _LOCK:
                _STATE.update({
                    "running": False,
                    "last_tick_at": datetime.now(timezone.utc).isoformat(),
                    "last_results": {"scheduler": {"status": "error", "error_type": type(exc).__name__}},
                    "tick_count": int(_STATE.get("tick_count") or 0) + 1,
                })
        elapsed = time.monotonic() - started
        time.sleep(max(1.0, tick_seconds() - elapsed))
    with _LOCK:
        _STATE["running"] = False


def reset_for_tests() -> None:
    global _THREAD
    with _LOCK:
        _STATE.update({
            "enabled": False,
            "running": False,
            "last_tick_at": None,
            "last_results": {},
            "tick_count": 0,
        })
        _THREAD = None
