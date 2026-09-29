from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

from .analysis_runner import run_analysis
from .circuit_breaker import for_source, reset_all as reset_circuit_breakers
from .dead_letter import best_effort_enqueue
from .observability import trace
from .sanctions_runtime import refresh_official_sanctions
from .satellite_runtime import refresh_celestrak
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
    "last_analysis_at": None,
    "last_analysis_result": None,
    "tick_count": 0,
    "analysis_count": 0,
}
_SANCTIONS_IDS = {"unsc_sanctions", "uk_sanctions"}
_NON_ANALYSIS_SOURCES = _SANCTIONS_IDS | {"ofac_sanctions", "wpi_ports", "celestrak"}


def enabled() -> bool:
    return os.environ.get("GEOWATCH_SOURCE_SCHEDULER", "").strip().casefold() in {"1", "true", "yes", "on"}


def tick_seconds() -> int:
    try:
        value = int(os.environ.get("GEOWATCH_SOURCE_SCHEDULER_TICK", "30"))
    except ValueError:
        value = 30
    return max(15, min(value, 300))


def analysis_min_interval_seconds() -> int:
    try:
        value = int(os.environ.get("GEOWATCH_ANALYSIS_MIN_INTERVAL_SECONDS", "300"))
    except ValueError:
        value = 300
    return max(60, min(value, 3600))


def analysis_config_path() -> str:
    return os.environ.get("GEOWATCH_ANALYSIS_CONFIG", "config/sources.production.json").strip() or "config/sources.production.json"


def status() -> dict[str, object]:
    with _LOCK:
        return {
            "schema_version": "geowatch-source-scheduler-status-v5",
            **_STATE,
            "enabled": enabled(),
            "tick_seconds": tick_seconds(),
            "analysis_min_interval_seconds": analysis_min_interval_seconds(),
            "analysis_config": analysis_config_path(),
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


def _execute_source(spec, sanctions_bundle: dict[str, object] | None) -> tuple[dict[str, object], dict[str, object] | None]:  # type: ignore[no-untyped-def]
    if spec.source_id in _SANCTIONS_IDS:
        if sanctions_bundle is None:
            sanctions_bundle = refresh_official_sanctions()
        bundle_results = sanctions_bundle.get("results") or {}
        result = (
            bundle_results.get(spec.source_id, {"status": "error", "error": "sanctions bundle missing source result"})
            if isinstance(bundle_results, dict)
            else {"status": "error", "error": "invalid sanctions result"}
        )
        return dict(result), sanctions_bundle
    if spec.source_id == "celestrak":
        return dict(refresh_celestrak(group="military")), sanctions_bundle
    if load_collection_spec(spec.source_id) is None:
        return {
            "status": "delegated",
            "runtime_mode": spec.runtime_mode,
            "implementation": spec.implementation,
        }, sanctions_bundle
    return dict(collect_source_once(spec.source_id)), sanctions_bundle


def _record_source_outcome(source_id: str, result: dict[str, object], *, at: datetime) -> dict[str, object]:
    breaker = for_source(source_id)
    status_value = str(result.get("status") or "").casefold()
    if status_value == "ok":
        breaker.record_success(now=at)
    elif status_value not in {"delegated", "skipped", "not_due"}:
        breaker.record_failure(now=at)
        message = str(result.get("error") or result.get("error_type") or "collector returned non-ok status")
        best_effort_enqueue(
            source_id=source_id,
            failure_class="collector",
            error=RuntimeError(message),
            request={"result_status": status_value},
            attempts=int(breaker.snapshot(now=at)["consecutive_failures"]),
            failed_at=at.isoformat(),
        )
    enriched = dict(result)
    enriched["circuit_breaker"] = breaker.snapshot(now=at)
    return enriched


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
    sanctions_bundle: dict[str, object] | None = None

    for spec in due:
        breaker = for_source(spec.source_id)
        if not breaker.allow_request(now=now):
            results[spec.source_id] = {
                "status": "circuit_open",
                "circuit_breaker": breaker.snapshot(now=now),
            }
            continue
        with trace("collector.run", attributes={"source_id": spec.source_id, "domain": spec.domain}):
            try:
                result, sanctions_bundle = _execute_source(spec, sanctions_bundle)
            except Exception as exc:
                breaker.record_failure(now=now)
                best_effort_enqueue(
                    source_id=spec.source_id,
                    failure_class="collector_exception",
                    error=exc,
                    request={"runtime_mode": spec.runtime_mode, "implementation": spec.implementation},
                    attempts=int(breaker.snapshot(now=now)["consecutive_failures"]),
                    failed_at=now.isoformat(),
                )
                result = {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:500],
                    "circuit_breaker": breaker.snapshot(now=now),
                }
            else:
                result = _record_source_outcome(spec.source_id, result, at=now)
            results[spec.source_id] = result

    should_analyze = _should_run_analysis(now, results)
    analysis_result: dict[str, object] | None = None
    if should_analyze:
        try:
            with trace("analysis.run", attributes={"config": analysis_config_path()}):
                analysis_result = {"status": "ok", **run_analysis(config_path=analysis_config_path())}
        except Exception as exc:
            analysis_result = {"status": "error", "error_type": type(exc).__name__, "error": str(exc)[:500]}
        with _LOCK:
            _STATE["last_analysis_at"] = datetime.now(timezone.utc).isoformat()
            _STATE["last_analysis_result"] = analysis_result
            _STATE["analysis_count"] = int(_STATE.get("analysis_count") or 0) + 1

    with _LOCK:
        _STATE.update({
            "running": False,
            "last_tick_at": now.isoformat(),
            "last_results": results,
            "tick_count": int(_STATE.get("tick_count") or 0) + 1,
        })
    return {
        "due": [spec.source_id for spec in due],
        "results": results,
        "analysis": analysis_result,
    }


def _should_run_analysis(now: datetime, results: dict[str, object]) -> bool:
    changed = any(
        source_id not in _NON_ANALYSIS_SOURCES
        and isinstance(result, dict)
        and result.get("status") == "ok"
        and int(result.get("records") or 0) > 0
        for source_id, result in results.items()
    )
    with _LOCK:
        last = _STATE.get("last_analysis_at")
    if last is None and any(isinstance(result, dict) and result.get("status") == "ok" for result in results.values()):
        return True
    if not changed:
        return False
    if not last:
        return True
    try:
        parsed = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        elapsed = (now - parsed.astimezone(timezone.utc)).total_seconds()
        return elapsed >= analysis_min_interval_seconds()
    except ValueError:
        return True


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
    reset_circuit_breakers()
    with _LOCK:
        _STATE.update({
            "enabled": False,
            "running": False,
            "last_tick_at": None,
            "last_results": {},
            "last_analysis_at": None,
            "last_analysis_result": None,
            "tick_count": 0,
            "analysis_count": 0,
        })
        _THREAD = None
