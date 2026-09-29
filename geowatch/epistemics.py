from __future__ import annotations

from typing import Literal

from .models import Event

EpistemicState = Literal["OBSERVADO", "RELATADO", "ESTIMADO", "INFERIDO", "NAO_CONFIRMADO"]

_VERIFICATION_CONFIDENCE = {
    "research_coded": 0.90,
    "curated_report": 0.75,
    "sensor_signal": 0.65,
    "osint_signal": 0.45,
}


def classify_event(event: Event) -> EpistemicState:
    if event.evidence_class == "inferred":
        return "INFERIDO"
    if event.evidence_class == "estimated":
        return "ESTIMADO"
    if event.verification_level == "sensor_signal":
        return "OBSERVADO"
    if event.verification_level in {"research_coded", "curated_report"}:
        return "RELATADO"
    return "NAO_CONFIRMADO"


def evidence_confidence_proxy(event: Event) -> float:
    """Transparent evidence-quality proxy, never a probability that the event is true."""
    base = _VERIFICATION_CONFIDENCE.get(event.verification_level, 0.35)
    if event.evidence_class == "inferred":
        base -= 0.15
    elif event.evidence_class == "estimated":
        base -= 0.08
    if event.latitude is not None and event.longitude is not None:
        base += 0.03
    if event.source_url:
        base += 0.02
    return round(max(0.0, min(base, 1.0)), 3)
