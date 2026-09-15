from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from .raw_store import open_raw_store
from .security_redaction import redact_runtime_secrets, redact_url
from .sources import celestrak
from .storage_factory import open_store


def refresh_celestrak(*, group: str = "military", db_path=None, raw_root="data/raw") -> dict[str, object]:
    source_id = "celestrak"
    collected_at = datetime.now(timezone.utc).isoformat()
    started_at = collected_at
    run_id = uuid4().hex
    store = open_store(db_path)
    raw_store = open_raw_store(raw_root)
    try:
        response_payload, response_url = celestrak.collect(group=group)
        safe_url = redact_url(response_url)
        raw_ref, digest = raw_store.put(
            source_id, collected_at, response_payload, "json",
            collector_id="celestrak_runtime", source_url=safe_url,
        )
        store.add_artifact(
            artifact_id=f"{source_id}:{digest}", source_id=source_id, sha256=digest,
            collected_at=collected_at, observed_url=safe_url, path=raw_ref,
            bytes_count=len(response_payload),
        )
        rows = celestrak.parse(response_payload)
        report_id = "sat_" + hashlib.sha256(f"{source_id}|{group}|{digest}".encode()).hexdigest()[:20]
        report = {
            "schema_version": "geowatch-satellite-catalog-v1",
            "report_id": report_id,
            "report_type": "satellite_catalog_celestrak",
            "generated_at": collected_at,
            "source_id": source_id,
            "group": group,
            "source_url": safe_url,
            "raw_ref": raw_ref,
            "sha256": digest,
            "satellite_count": len(rows),
            "satellites": [row.to_dict() for row in rows],
            "semantics": {
                "catalog_not_imagery": True,
                "orbital_elements_not_current_ground_position": True,
                "no_intent_inference": True,
                "refresh_policy": "CelesTrak data is reused and refreshed no more frequently than the provider's documented update cadence.",
            },
        }
        store.upsert_report(report, "")
        store.update_checkpoint(source_id, last_success_at=collected_at, last_reference_at=collected_at, cursor={"sha256": digest, "group": group})
        finished_at = datetime.now(timezone.utc).isoformat()
        store.record_run(
            run_id=run_id, source_id=source_id, started_at=started_at, finished_at=finished_at,
            status="ok", records=len(rows), request={"kind": "celestrak", "group": group},
        )
        return {"source_id": source_id, "status": "ok", "records": len(rows), "sha256": digest, "report_id": report_id}
    except Exception as exc:
        finished_at = datetime.now(timezone.utc).isoformat()
        error = redact_runtime_secrets(f"{type(exc).__name__}: {exc}")
        store.record_run(
            run_id=run_id, source_id=source_id, started_at=started_at, finished_at=finished_at,
            status="error", records=0, request={"kind": "celestrak", "group": group}, error=error,
        )
        return {"source_id": source_id, "status": "error", "error": error}
    finally:
        store.close()
