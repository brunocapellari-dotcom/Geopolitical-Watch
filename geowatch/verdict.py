from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

Verdict = Literal["CONFIRMADO", "PROVÁVEL", "NÃO VERIFICADO", "CONFLITANTE", "FALSO"]


@dataclass(frozen=True)
class VerdictInput:
    claim_id: str
    timestamp_quality: float
    geolocation_quality: float
    source_count: int
    independent_source_count: int
    physical_evidence_count: int
    official_source_count: int
    support_count: int
    refute_count: int
    source_reliability: float
    physical_evidence_quality: float = 0.0
    explicit_retraction: bool = False


@dataclass(frozen=True)
class VerdictResult:
    claim_id: str
    verdict: Verdict
    confidence: int
    method_version: str
    factors: dict[str, object]
    rationale: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["rationale"] = list(self.rationale)
        return row


def assess_claim(value: VerdictInput) -> VerdictResult:
    _validate(value)

    corroboration = min(1.0, value.independent_source_count / 3.0)
    physical = min(1.0, max(value.physical_evidence_quality, min(1.0, value.physical_evidence_count / 2.0)))
    official = min(1.0, value.official_source_count / 2.0)
    support_balance = value.support_count / max(1, value.support_count + value.refute_count)
    contradiction_ratio = value.refute_count / max(1, value.support_count + value.refute_count)

    base = (
        _clip(value.timestamp_quality) * 0.12
        + _clip(value.geolocation_quality) * 0.16
        + corroboration * 0.24
        + physical * 0.18
        + official * 0.10
        + _clip(value.source_reliability) * 0.14
        + support_balance * 0.06
    )
    contradiction_penalty = min(0.55, contradiction_ratio * 0.55)
    confidence = round(max(0.0, min(1.0, base * (1.0 - contradiction_penalty))) * 100)

    rationale: list[str] = []
    if value.independent_source_count >= 2:
        rationale.append("multiple independent sources")
    elif value.source_count > 1:
        rationale.append("multiple reports but independence is not established")
    if value.physical_evidence_count:
        rationale.append("physical or sensor evidence is present")
    if value.official_source_count:
        rationale.append("official or primary-source evidence is present")
    if value.refute_count:
        rationale.append("credible refuting evidence is present")
    if value.explicit_retraction:
        rationale.append("an explicit retraction or correction is recorded")

    strong_refutation = (
        value.refute_count >= 2
        and value.support_count == 0
        and (value.official_source_count >= 1 or value.source_reliability >= 0.8)
    )
    contradictory = value.support_count > 0 and value.refute_count > 0
    confirmed_gate = (
        value.independent_source_count >= 2
        and (value.physical_evidence_count >= 1 or value.official_source_count >= 1)
        and value.timestamp_quality >= 0.7
        and value.geolocation_quality >= 0.65
        and value.refute_count == 0
        and confidence >= 78
    )
    probable_gate = (
        value.independent_source_count >= 2
        and value.support_count >= 2
        and value.source_reliability >= 0.55
        and confidence >= 58
        and value.refute_count == 0
    ) or (
        value.independent_source_count >= 1
        and value.physical_evidence_count >= 1
        and value.support_count >= 1
        and value.source_reliability >= 0.65
        and confidence >= 58
        and value.refute_count == 0
    )

    if value.explicit_retraction and value.support_count == 0:
        verdict: Verdict = "FALSO"
        confidence = max(confidence, 85)
        rationale.append("the live claim is superseded by a retraction")
    elif strong_refutation:
        verdict = "FALSO"
        confidence = max(confidence, 80)
        rationale.append("independent refutation meets the false-claim gate")
    elif contradictory:
        verdict = "CONFLITANTE"
        confidence = min(confidence, 74)
        rationale.append("supporting and refuting evidence coexist")
    elif confirmed_gate:
        verdict = "CONFIRMADO"
        rationale.append("confirmation gate met: independent corroboration plus physical/official evidence")
    elif probable_gate:
        verdict = "PROVÁVEL"
        rationale.append("probability gate met, but confirmation requirements are incomplete")
    else:
        verdict = "NÃO VERIFICADO"
        rationale.append("evidence is insufficient for a stronger verdict")

    return VerdictResult(
        claim_id=value.claim_id,
        verdict=verdict,
        confidence=max(0, min(int(confidence), 100)),
        method_version="geowatch-verdict-v1",
        factors={
            "timestamp_quality": round(value.timestamp_quality, 3),
            "geolocation_quality": round(value.geolocation_quality, 3),
            "source_count": value.source_count,
            "independent_source_count": value.independent_source_count,
            "physical_evidence_count": value.physical_evidence_count,
            "official_source_count": value.official_source_count,
            "support_count": value.support_count,
            "refute_count": value.refute_count,
            "source_reliability": round(value.source_reliability, 3),
            "physical_evidence_quality": round(value.physical_evidence_quality, 3),
            "explicit_retraction": value.explicit_retraction,
            "corroboration_score": round(corroboration, 3),
            "contradiction_ratio": round(contradiction_ratio, 3),
        },
        rationale=tuple(rationale),
    )


def operational_event_contract(
    *,
    what: str,
    where: str | None,
    when: str | None,
    who: list[str] | tuple[str, ...],
    sources: list[str] | tuple[str, ...],
    evidence: list[str] | tuple[str, ...],
    verdict: VerdictResult,
) -> dict[str, object]:
    """Canonical presentation contract for a relevant event.

    Every event can be rendered with WHAT / WHERE / WHEN / WHO / SOURCE /
    EVIDENCE / CONFIDENCE / STATUS without implying that absent fields are known.
    """
    return {
        "what": what,
        "where": where,
        "when": when,
        "who": list(who),
        "source": list(sources),
        "evidence": list(evidence),
        "confidence": verdict.confidence,
        "status": verdict.verdict,
        "verdict_method": verdict.method_version,
    }


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _validate(value: VerdictInput) -> None:
    if not value.claim_id.strip():
        raise ValueError("claim_id is required")
    for name in ("timestamp_quality", "geolocation_quality", "source_reliability", "physical_evidence_quality"):
        number = float(getattr(value, name))
        if number < 0.0 or number > 1.0:
            raise ValueError(f"{name} must be between 0 and 1")
    for name in (
        "source_count",
        "independent_source_count",
        "physical_evidence_count",
        "official_source_count",
        "support_count",
        "refute_count",
    ):
        if int(getattr(value, name)) < 0:
            raise ValueError(f"{name} must be non-negative")
    if value.independent_source_count > value.source_count:
        raise ValueError("independent_source_count cannot exceed source_count")
