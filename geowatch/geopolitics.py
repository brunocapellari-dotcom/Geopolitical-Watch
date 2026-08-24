from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable

from .models import Claim, ConflictEpisode, Entity, Event


class GeopoliticalKnowledge:
    """Deterministic geopolitical context retrieval.

    This engine retrieves analytical context only. Returned material is explicitly
    marked as non-evidentiary and must never increase evidence strength or verify a
    factual claim.
    """

    def __init__(self, knowledge: dict, sources: dict | None = None) -> None:
        self.knowledge = knowledge
        self.sources = sources or {}
        self.concepts = {row["id"]: row for row in knowledge.get("concepts", [])}
        self.schools = {row["id"]: row for row in knowledge.get("schools", [])}
        self.regions = {row["id"]: row for row in knowledge.get("regions", [])}
        self.case_studies = {row["id"]: row for row in knowledge.get("case_studies", [])}

    @classmethod
    def from_files(
        cls,
        knowledge_path: str | Path = "config/geopolitics/knowledge.json",
        sources_path: str | Path = "config/geopolitics/sources.json",
    ) -> "GeopoliticalKnowledge":
        knowledge = json.loads(Path(knowledge_path).read_text(encoding="utf-8"))
        sources_file = Path(sources_path)
        sources = json.loads(sources_file.read_text(encoding="utf-8")) if sources_file.exists() else {}
        return cls(knowledge, sources)

    @property
    def knowledge_version(self) -> str:
        return str(self.knowledge.get("schema_version", "unknown"))

    @property
    def source_registry_version(self) -> str:
        return str(self.sources.get("schema_version", "unknown"))

    def context_for_episode(
        self,
        episode: ConflictEpisode,
        *,
        claims: Iterable[Claim] = (),
        entities: Iterable[Entity] = (),
        events: Iterable[Event] = (),
        max_concepts: int = 8,
        max_cases: int = 3,
    ) -> dict:
        claims = list(claims)
        entities = list(entities)
        events = list(events)
        corpus = self._episode_corpus(episode, claims, entities, events)

        concept_scores: list[tuple[int, str, dict]] = []
        for concept_id, concept in self.concepts.items():
            hits = []
            for keyword in concept.get("keywords", []):
                normalized = _norm(str(keyword))
                if normalized and _contains_phrase(corpus, normalized):
                    hits.append(str(keyword))
            if hits:
                concept_scores.append((len(hits), concept_id, {**concept, "matched_keywords": hits}))
        concept_scores.sort(key=lambda row: (-row[0], row[1]))
        matched = [row[2] for row in concept_scores[:max_concepts]]
        matched_ids = {row["id"] for row in matched}

        regional = []
        episode_countries = set(episode.countries)
        for region in self.regions.values():
            countries = set(region.get("countries") or [])
            overlap = sorted(episode_countries & countries)
            if overlap:
                regional.append({
                    "id": region["id"],
                    "matched_countries": overlap,
                    "themes": list(region.get("themes") or []),
                })

        theories = []
        for school in self.schools.values():
            focus = set(school.get("focus") or [])
            overlap = sorted(focus & matched_ids)
            if overlap:
                theories.append({
                    "id": school["id"],
                    "name": school["name"],
                    "matched_concepts": overlap,
                    "cautions": list(school.get("cautions") or []),
                })

        cases: list[tuple[int, dict]] = []
        for case in self.case_studies.values():
            themes = set(case.get("themes") or [])
            overlap = sorted(themes & matched_ids)
            if overlap:
                cases.append((len(overlap), {
                    "id": case["id"],
                    "period": case.get("period"),
                    "shared_mechanisms": overlap,
                    "analogy_limits": list(case.get("analogy_limits") or []),
                }))
        cases.sort(key=lambda row: (-row[0], row[1]["id"]))

        questions: list[str] = []
        for concept in matched:
            for question in concept.get("questions", []):
                if question not in questions:
                    questions.append(str(question))

        return {
            "context_not_evidence": True,
            "knowledge_version": self.knowledge_version,
            "source_registry_version": self.source_registry_version,
            "matched_concepts": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "matched_keywords": row.get("matched_keywords", []),
                    "mechanisms": row.get("mechanisms", []),
                }
                for row in matched
            ],
            "theoretical_lenses": theories,
            "regional_context": regional,
            "historical_analogies": [row[1] for row in cases[:max_cases]],
            "analytical_questions": questions[:20],
            "methodology_notes": [
                "Strategic context is retrieved from durable knowledge and is not evidence that the episode or any claim occurred.",
                "Historical analogies are mechanism prompts, not forecasts; analogy limits must be retained.",
                "Multiple theoretical lenses may be simultaneously valid and should not be collapsed into a single causal story without evidence.",
            ],
        }

    @staticmethod
    def _episode_corpus(
        episode: ConflictEpisode,
        claims: list[Claim],
        entities: list[Entity],
        events: list[Event],
    ) -> str:
        chunks: list[str] = [episode.title, episode.state, *episode.countries, *episode.regions]
        chunks.extend(claim.statement for claim in claims)
        chunks.extend(claim.claim_type for claim in claims)
        chunks.extend(entity.canonical_name for entity in entities)
        chunks.extend(entity.entity_type for entity in entities)
        chunks.extend(event.title for event in events)
        chunks.extend(area for event in events for area in event.impact_areas)
        return _norm(" ".join(str(value) for value in chunks if value))


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _contains_phrase(corpus: str, phrase: str) -> bool:
    if not phrase:
        return False
    return f" {phrase} " in f" {corpus} "
