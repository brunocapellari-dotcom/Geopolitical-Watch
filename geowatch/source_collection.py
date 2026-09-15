from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .pipeline import _collect_incremental
from .raw_store import open_raw_store
from .security_redaction import redact_runtime_secrets, redact_url
from .storage_factory import open_store

_DEFAULT_CONFIGS = (
    "config/sources.production.json",
    "config/sources.json",
    "config/sources.public-beta.json",
)


def load_collection_spec(source_id: str, config_paths: tuple[str, ...] = _DEFAULT_CONFIGS) -> tuple[dict, dict] | None:
    for path in config_paths:
        file = Path(path)
        if not file.exists():
            continue
        config = json.loads(file.read_text(encoding="utf-8"))
        for row in config.get("sources", []):
            if row.get("source_id") == source_id:
                return dict(row), dict(config.get("history") or {})
    return None


def collect_source_once(
    source_id: str,
    *,
    db_path: str | Path | None = None,
    raw_root: str | Path = "data/raw",
) -> dict[str, object]:
    loaded = load_collection_spec(source_id)
    if loaded is None:
        return {"source_id": source_id, "status": "unsupported", "reason": "no collection adapter configuration"}
    spec, history_cfg = loaded
    kind = str(spec.get("kind") or source_id)
    collector_id = str(spec.get("collector_id") or f"{kind}_collector")
    default_lookback_hours = int(history_cfg.get("default_lookback_hours", 24))
    overlap_minutes = int(history_cfg.get("checkpoint_overlap_minutes", 30))
    now = datetime.now(timezone.utc)
    collected_at = now.isoformat()
    started_at = collected_at
    run_id = uuid4().hex
    store = open_store(db_path)
    raw_store = open_raw_store(raw_root)
    request_meta: dict[str, object] = {"kind": kind, "collector_id": collector_id, "scheduler": "source_registry"}
    try:
        checkpoint = store.get_checkpoint(source_id)
        payloads, urls, parser = _collect_incremental(
            spec,
            checkpoint=checkpoint,
            now=now,
            default_lookback_hours=default_lookback_hours,
            overlap_minutes=overlap_minutes,
            request_meta=request_meta,
        )
        events = []
        safe_urls: list[str] = []
        for index, payload in enumerate(payloads):
            url = urls[index] if index < len(urls) else None
            safe_url = redact_url(url) if url else None
            if safe_url:
                safe_urls.append(safe_url)
            raw_ref, digest = raw_store.put(
                source_id,
                collected_at,
                payload,
                str(spec.get("extension", "json")),
                collector_id=collector_id,
                source_url=safe_url,
            )
            store.add_artifact(
                artifact_id=f"{source_id}:{digest}",
                source_id=source_id,
                sha256=digest,
                collected_at=collected_at,
                observed_url=safe_url,
                path=raw_ref,
                bytes_count=len(payload),
            )
            events.extend(parser(payload, source_id=source_id, collected_at=collected_at, raw_ref=raw_ref))
        store.upsert_events(events)
        last_reference = max((event.reference_at for event in events), default=None)
        store.update_checkpoint(
            source_id,
            last_success_at=collected_at,
            last_reference_at=last_reference,
            cursor={"observed_urls": safe_urls[-3:]},
        )
        finished_at = datetime.now(timezone.utc).isoformat()
        store.record_run(
            run_id=run_id,
            source_id=source_id,
            started_at=started_at,
            finished_at=finished_at,
            status="ok",
            records=len(events),
            request=request_meta,
        )
        return {
            "source_id": source_id,
            "status": "ok",
            "records": len(events),
            "requests": len(payloads),
            "collector_id": collector_id,
            "finished_at": finished_at,
        }
    except Exception as exc:
        finished_at = datetime.now(timezone.utc).isoformat()
        error = redact_runtime_secrets(f"{type(exc).__name__}: {exc}")
        store.record_run(
            run_id=run_id,
            source_id=source_id,
            started_at=started_at,
            finished_at=finished_at,
            status="error",
            records=0,
            request=request_meta,
            error=error,
        )
        return {"source_id": source_id, "status": "error", "error": error, "finished_at": finished_at}
    finally:
        store.close()
