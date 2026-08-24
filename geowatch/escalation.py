from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable

from .models import Claim, Event


class EscalationLibrary:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.indicators = list(payload.get("indicators", []))

    @classmethod
    def from_json(cls, path: str | Path = "config/geopolitics/escalation_indicators.json") -> "EscalationLibrary":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def detect(self, *, events: Iterable[Event] = (), claims: Iterable[Claim] = ()) -> dict:
        corpus = _norm(" ".join(
            [event.title for event in events]
            + [claim.statement for claim in claims]
            + [claim.claim_type for claim in claims]
        ))
        matches = []
        escalation_score = 0
        deescalation_score = 0
        pressure_score = 0
        for indicator in self.indicators:
            hits = [kw for kw in indicator.get("keywords", []) if _contains(corpus, _norm(str(kw)))]
            if not hits:
                continue
            weight = int(indicator.get("weight", 1))
            direction = str(indicator.get("direction", "context"))
            if direction == "escalation":
                escalation_score += weight
            elif direction == "deescalation":
                deescalation_score += weight
            elif direction == "pressure":
                pressure_score += weight
            matches.append({
                "id": indicator["id"], "direction": direction, "weight": weight,
                "matched_keywords": hits, "questions": list(indicator.get("questions", [])),
            })
        net = escalation_score - deescalation_score
        return {
            "schema_version": "geowatch-escalation-readout-v1",
            "indicator_count": len(matches),
            "escalation_points": escalation_score,
            "deescalation_points": deescalation_score,
            "pressure_points": pressure_score,
            "net_directional_points": net,
            "indicators": matches,
            "indicator_score_not_probability": True,
            "methodology_notes": [
                "Indicators are analytical observables, not proof of intent or future action.",
                "Routine exercises, rotations, precautionary measures and reporting artifacts can mimic escalation signals.",
                "Use baselines, source evidence and competing hypotheses before drawing strategic conclusions.",
            ],
        }


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _contains(corpus: str, phrase: str) -> bool:
    return bool(phrase) and f" {phrase} " in f" {corpus} "
