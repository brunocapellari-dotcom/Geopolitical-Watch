from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from .http import get
from .raw_store import open_raw_store
from .sanctions_feed import SanctionsDesignation, diff_designations, parse_uk_csv, parse_un_consolidated_xml
from .security_redaction import redact_runtime_secrets, redact_url
from .storage_factory import open_store

_UN_URL = "https://scsanctions.un.org/resources/xml/en/name/consolidated.xml"
_UK_URL = "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.csv"


def refresh_official_sanctions(*, db_path=None, raw_root="data/raw") -> dict[str, object]:
    collected_at = datetime.now(timezone.utc).isoformat()
    store = open_store(db_path)
    raw_store = open_raw_store(raw_root)
    results: dict[str, object] = {}
    try:
        for source_id, authority, url, extension, parser in (
            ("unsc_sanctions", "UNSC", _UN_URL, "xml", parse_un_consolidated_xml),
            ("uk_sanctions", "UK-FCDO", _UK_URL, "csv", parse_uk_csv),
        ):
            run_id = uuid4().hex
            started_at = datetime.now(timezone.utc).isoformat()
            try:
                response = get(url, timeout=180, retries=2, backoff_seconds=2.0)
                safe_url = redact_url(response.url)
                raw_ref, digest = raw_store.put(
                    source_id, collected_at, response.payload, extension,
                    collector_id="official_sanctions_runtime", source_url=safe_url,
                )
                store.add_artifact(
                    artifact_id=f"{source_id}:{digest}", source_id=source_id, sha256=digest,
                    collected_at=collected_at, observed_url=safe_url, path=raw_ref,
                    bytes_count=len(response.payload),
                )
                rows = _dedupe(parser(response.payload, collected_at=collected_at, source_url=safe_url))
                report_type = f"sanctions_snapshot_{source_id}"
                previous = store.latest_report(report_type)
                previous_rows = _objects(previous.get("designations", [])) if previous else []
                diff = diff_designations(previous_rows, rows) if previous_rows else {
                    "added": [], "removed": [], "modified": [], "unchanged": 0,
                    "baseline_snapshot": True,
                    "legal_effect_requires_authority_specific_review": True,
                }
                report_id = "sanc_" + hashlib.sha256(f"{source_id}|{digest}".encode()).hexdigest()[:20]
                report = {
                    "schema_version": "geowatch-sanctions-runtime-v1",
                    "report_id": report_id,
                    "report_type": report_type,
                    "generated_at": collected_at,
                    "source_id": source_id,
                    "authority": authority,
                    "source_url": safe_url,
                    "raw_ref": raw_ref,
                    "sha256": digest,
                    "designation_count": len(rows),
                    "designations": [row.to_dict() for row in rows],
                    "diff": diff,
                    "governance": {
                        "official_designation_record_only": True,
                        "legal_effect_requires_jurisdiction_specific_review": True,
                        "designation_not_conflict_event_evidence": True,
                    },
                }
                store.upsert_report(report, "")
                store.update_checkpoint(source_id, last_success_at=collected_at, last_reference_at=collected_at, cursor={"sha256": digest})
                finished_at = datetime.now(timezone.utc).isoformat()
                store.record_run(
                    run_id=run_id, source_id=source_id, started_at=started_at, finished_at=finished_at,
                    status="ok", records=len(rows), request={"kind": "sanctions", "authority": authority},
                )
                results[source_id] = {
                    "status": "ok", "records": len(rows), "sha256": digest,
                    "added": len(diff.get("added", [])), "removed": len(diff.get("removed", [])),
                    "modified": len(diff.get("modified", [])),
                }
            except Exception as exc:
                finished_at = datetime.now(timezone.utc).isoformat()
                error = redact_runtime_secrets(f"{type(exc).__name__}: {exc}")
                store.record_run(
                    run_id=run_id, source_id=source_id, started_at=started_at, finished_at=finished_at,
                    status="error", records=0, request={"kind": "sanctions", "authority": authority}, error=error,
                )
                results[source_id] = {"status": "error", "error": error}
        return {"generated_at": collected_at, "results": results}
    finally:
        store.close()


def _dedupe(rows: list[SanctionsDesignation]) -> list[SanctionsDesignation]:
    return list({row.designation_id: row for row in rows}.values())


def _objects(rows: list[dict]) -> list[SanctionsDesignation]:
    output: list[SanctionsDesignation] = []
    for row in rows:
        output.append(SanctionsDesignation(
            designation_id=str(row["designation_id"]), authority=str(row["authority"]),
            list_name=str(row["list_name"]), external_reference=row.get("external_reference"),
            name=str(row["name"]), entity_type=str(row.get("entity_type") or "unknown"),
            programs=tuple(row.get("programs") or ()), effective_date=row.get("effective_date"),
            source_url=row.get("source_url"), collected_at=str(row.get("collected_at") or ""),
            evidence_class=str(row.get("evidence_class") or "observed"),
        ))
    return output
