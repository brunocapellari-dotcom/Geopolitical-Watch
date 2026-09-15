from __future__ import annotations

import os

from .collector_scheduler import status as scheduler_status
from .embedded_collector import status as collector_status
from .live_vessels import provider_status as vessel_status
from .raw_store import raw_backend_name
from .storage_factory import backend_name


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def build_runtime_readiness() -> dict:
    database_backend = backend_name()
    raw_backend = raw_backend_name()
    collector = collector_status()
    scheduler = scheduler_status()
    vessels = vessel_status()
    embedded_enabled = bool(collector.get("enabled"))
    scheduler_enabled = bool(scheduler.get("enabled"))
    exactly_one_collector = embedded_enabled ^ scheduler_enabled

    checks = {
        "private_auth_configured": len(os.environ.get("GEOWATCH_API_TOKEN", "")) >= 32,
        "persistent_structured_database": database_backend == "postgresql-postgis",
        "persistent_raw_evidence": raw_backend in {"postgresql-compressed", "gcs"},
        "collection_path_configured": exactly_one_collector,
        "duplicate_collectors_disabled": not (embedded_enabled and scheduler_enabled),
        "runtime_wpi_enabled": _flag("GEOWATCH_WPI_RUNTIME"),
        "ais_credentials_configured": bool(vessels.get("configured")),
        "always_on_compute_declared": _flag("GEOWATCH_ALWAYS_ON"),
    }

    private_web_ready = all(checks[key] for key in (
        "private_auth_configured",
        "persistent_structured_database",
        "persistent_raw_evidence",
        "collection_path_configured",
        "duplicate_collectors_disabled",
    ))
    live_aircraft_ready = private_web_ready
    continuous_ais_ready = private_web_ready and checks["ais_credentials_configured"] and checks["always_on_compute_declared"]

    blockers = []
    labels = {
        "private_auth_configured": "GEOWATCH_API_TOKEN must be configured with at least 32 characters",
        "persistent_structured_database": "persistent PostgreSQL/PostGIS is not active",
        "persistent_raw_evidence": "RAW evidence is still using ephemeral filesystem storage",
        "collection_path_configured": "exactly one batch collection mode must be enabled",
        "duplicate_collectors_disabled": "legacy embedded collector and registry scheduler cannot run together",
        "runtime_wpi_enabled": "runtime WPI enrichment is disabled",
        "ais_credentials_configured": "AISSTREAM_API_KEY is not configured",
        "always_on_compute_declared": "compute is not declared always-on; continuous AIS cannot be guaranteed",
    }
    for key, passed in checks.items():
        if not passed:
            blockers.append({"check": key, "detail": labels[key]})

    collection_mode = "registry_scheduler" if scheduler_enabled and not embedded_enabled else "legacy_embedded" if embedded_enabled and not scheduler_enabled else "invalid" if embedded_enabled and scheduler_enabled else "none"
    return {
        "schema_version": "geowatch-runtime-readiness-v2",
        "checks": checks,
        "private_web_ready": private_web_ready,
        "live_aircraft_ready": live_aircraft_ready,
        "continuous_ais_ready": continuous_ais_ready,
        "database_backend": database_backend,
        "raw_backend": raw_backend,
        "collection_mode": collection_mode,
        "collector": collector,
        "source_scheduler": scheduler,
        "vessels": {
            "provider": vessels.get("provider"),
            "configured": vessels.get("configured"),
            "connected": vessels.get("connected"),
            "vessel_count": vessels.get("vessel_count"),
            "last_message_at": vessels.get("last_message_at"),
            "last_error": vessels.get("last_error"),
        },
        "blockers": blockers,
        "semantics": {
            "private_web_ready": "private dashboard, persistent structured/raw data, and exactly one collection path are configured",
            "live_aircraft_ready": "aircraft data can be fetched on demand through the private backend",
            "continuous_ais_ready": "AIS credentials and an explicitly always-on compute runtime are both present",
            "collection_mode": "registry_scheduler is preferred; legacy_embedded exists only as rollback compatibility",
        },
    }
