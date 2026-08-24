from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    episode_id: str
    statement: str
    status: str = "open"
    indicators_for: tuple[str, ...] = ()
    indicators_against: tuple[str, ...] = ()
    discriminating_indicators: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        row = asdict(self)
        for key in ("indicators_for", "indicators_against", "discriminating_indicators", "assumptions"):
            row[key] = list(getattr(self, key))
        return row


def make_hypothesis(episode_id: str, statement: str, **kwargs) -> Hypothesis:
    hid = "hyp_" + hashlib.sha256(f"{episode_id}|{statement}".encode()).hexdigest()[:20]
    return Hypothesis(hypothesis_id=hid, episode_id=episode_id, statement=statement, **kwargs)


def score_hypotheses(hypotheses: Iterable[Hypothesis], observed_indicators: Iterable[str]) -> list[dict]:
    """Rank diagnostic fit without turning it into probability.

    Scores compare support/contradiction counts only. They are not posterior probabilities.
    """
    observed = set(observed_indicators)
    rows = []
    for hypothesis in hypotheses:
        supporting = sorted(observed & set(hypothesis.indicators_for))
        contradicting = sorted(observed & set(hypothesis.indicators_against))
        discriminating = sorted(observed & set(hypothesis.discriminating_indicators))
        diagnostic_score = len(supporting) + 2 * len(discriminating) - 2 * len(contradicting)
        rows.append({
            **hypothesis.to_dict(),
            "supporting_observed": supporting,
            "contradicting_observed": contradicting,
            "discriminating_observed": discriminating,
            "diagnostic_score": diagnostic_score,
            "score_not_probability": True,
        })
    rows.sort(key=lambda row: (-int(row["diagnostic_score"]), str(row["hypothesis_id"])))
    return rows


def hypothesis_template(episode_id: str, statements: Iterable[str]) -> dict:
    hypotheses = [make_hypothesis(episode_id, statement) for statement in statements]
    return {
        "schema_version": "geowatch-competing-hypotheses-v1",
        "episode_id": episode_id,
        "hypotheses": [row.to_dict() for row in hypotheses],
        "methodology_notes": [
            "Keep at least two plausible hypotheses when material uncertainty remains.",
            "Seek evidence that discriminates between hypotheses, not only evidence that confirms the leading view.",
            "Diagnostic scores are not probabilities and do not replace source/evidence review.",
        ],
    }
