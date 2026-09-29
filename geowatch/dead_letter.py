from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .storage_factory import open_store


def deterministic_dead_letter_id(
    *,
    source_id: str,
    failed_at: str,
    failure_class: str,
    error_type: str | None,
) -> str:
    seed = "|".join((source_id, failed_at, failure_class, error_type or ""))
    return "dlq_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def enqueue_failure(
    *,
    source_id: str,
    failure_class: str,
    error: BaseException | None = None,
    request: dict[str, object] | None = None,
    payload_ref: str | None = None,
    attempts: int = 1,
    failed_at: str | None = None,
) -> bool:
    timestamp = failed_at or datetime.now(timezone.utc).isoformat()
    error_type = type(error).__name__ if error is not None else None
    error_message = str(error)[:2000] if error is not None else None
    dead_letter_id = deterministic_dead_letter_id(
        source_id=source_id,
        failed_at=timestamp,
        failure_class=failure_class,
        error_type=error_type,
    )
    store = open_store()
    try:
        writer = getattr(store, "enqueue_dead_letter", None)
        if writer is None:
            return False
        return bool(writer(
            dead_letter_id=dead_letter_id,
            source_id=source_id,
            failed_at=timestamp,
            failure_class=failure_class,
            error_type=error_type,
            error_message=error_message,
            request=request,
            payload_ref=payload_ref,
            attempts=max(1, int(attempts)),
        ))
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def best_effort_enqueue(**kwargs) -> bool:  # type: ignore[no-untyped-def]
    try:
        return enqueue_failure(**kwargs)
    except Exception:
        return False
