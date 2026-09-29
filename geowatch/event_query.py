from __future__ import annotations

from collections.abc import Iterable

from .core import normalize_text
from .epistemics import classify_event, evidence_confidence_proxy
from .models import Event


def filter_event_records(
    events: Iterable[Event],
    *,
    region: str | None = None,
    actor: str | None = None,
    event_type: str | None = None,
    source_id: str | None = None,
    epistemic_state: str | None = None,
    min_confidence: float | None = None,
) -> list[dict[str, object]]:
    region_key = normalize_text(region or "")
    actor_key = normalize_text(actor or "")
    type_key = normalize_text(event_type or "")
    source_key = normalize_text(source_id or "")
    epi_key = (epistemic_state or "").strip().upper()
    minimum = None if min_confidence is None else max(0.0, min(float(min_confidence), 1.0))

    rows: list[dict[str, object]] = []
    for event in events:
        confidence = evidence_confidence_proxy(event)
        epistemic = classify_event(event)
        if region_key and region_key not in normalize_text(" ".join(filter(None, (event.region, event.country)))):
            continue
        if actor_key and not any(actor_key in normalize_text(value) for value in event.actors):
            continue
        if type_key and type_key != normalize_text(event.event_type):
            continue
        if source_key and source_key != normalize_text(event.source_id):
            continue
        if epi_key and epi_key != epistemic:
            continue
        if minimum is not None and confidence < minimum:
            continue
        row = event.to_dict()
        row["epistemic_state"] = epistemic
        row["evidence_confidence_proxy"] = confidence
        row["confidence_note"] = "evidence-quality proxy; not probability of truth"
        rows.append(row)
    return rows
