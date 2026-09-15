from __future__ import annotations

from datetime import datetime, timezone

from .history import parse_utc
from .source_registry import SourceRegistry, load_registry


def build_source_health(store, *, registry: SourceRegistry | None = None, now: datetime | None = None) -> dict[str, object]:
    registry = registry or load_registry()
    current = now or datetime.now(timezone.utc)
    rows: list[dict[str, object]] = []
    counts: dict[str, int] = {}
    for spec in registry.specs:
        checkpoint = store.get_checkpoint(spec.source_id)
        last_success = checkpoint.get("last_success_at") if checkpoint else None
        age_seconds = None
        if last_success:
            try:
                age_seconds = max(0, int((current - parse_utc(str(last_success))).total_seconds()))
            except (TypeError, ValueError):
                age_seconds = None
        status = _status(spec.activation, spec.runtime_mode, spec.can_run, age_seconds, spec.cadence_seconds)
        counts[status] = counts.get(status, 0) + 1
        rows.append({
            "source_id": spec.source_id,
            "name": spec.name,
            "domain": spec.domain,
            "owner_ai": spec.owner_ai,
            "runtime_mode": spec.runtime_mode,
            "activation": spec.activation,
            "status": status,
            "cadence_seconds": spec.cadence_seconds,
            "last_success_at": last_success,
            "age_seconds": age_seconds,
            "missing_credentials": list(spec.missing_credentials()),
            "evidence_role": spec.evidence_role,
        })
    return {
        "schema_version": "geowatch-source-health-v1",
        "generated_at": current.isoformat(),
        "counts": counts,
        "sources": rows,
    }


def _status(activation: str, runtime_mode: str, can_run: bool, age_seconds: int | None, cadence_seconds: int) -> str:
    if activation.startswith("blocked"):
        return "blocked"
    if activation.startswith("planned") or activation in {"reference", "family"}:
        return "planned"
    if runtime_mode in {"pull_on_view", "continuous_stream", "reference_only", "registry_family"}:
        return "delegated"
    if not can_run:
        return "inactive"
    if age_seconds is None:
        return "starting"
    if age_seconds > max(cadence_seconds * 3, cadence_seconds + 300):
        return "stale"
    return "healthy"
