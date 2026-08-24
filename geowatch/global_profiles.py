from __future__ import annotations

import json
from pathlib import Path


class GlobalProfileRegistry:
    """Global country/territory coverage without pretending full enrichment.

    The ISO registry gives namespace coverage. Strategic profiles remain separately
    curated, sourced and dated. A baseline row is context only and cannot verify facts.
    """

    def __init__(self, registry: dict, enriched: dict) -> None:
        self.registry = registry
        self.enriched = enriched
        self._names = {code: name for code, name in registry.get("countries", [])}
        self._profiles = {row["country_id"]: row for row in enriched.get("profiles", [])}

    @classmethod
    def from_files(cls, registry_path: str | Path = "config/geopolitics/country_registry.json", enriched_path: str | Path = "config/geopolitics/country_profiles.json") -> "GlobalProfileRegistry":
        return cls(
            json.loads(Path(registry_path).read_text(encoding="utf-8")),
            json.loads(Path(enriched_path).read_text(encoding="utf-8")),
        )

    def profile(self, country_id: str) -> dict | None:
        code = country_id.upper()
        if code not in self._names:
            return None
        if code in self._profiles:
            return {**self._profiles[code], "profile_status": "enriched", "context_not_evidence": True}
        return {
            "country_id": code,
            "name": self._names[code],
            "profile_status": "baseline_needs_enrichment",
            "context_not_evidence": True,
            "strategic_themes": [],
            "exposures": [],
            "questions": ["Which structural interests, dependencies, alliances and vulnerabilities require sourced enrichment?"],
            "source_ids": [],
        }

    def coverage(self) -> dict:
        total = len(self._names)
        enriched = len(set(self._profiles) & set(self._names))
        return {
            "schema_version": "geowatch-country-profile-coverage-v1",
            "registry_count": total,
            "enriched_count": enriched,
            "enrichment_ratio": round(enriched / total, 4) if total else 0.0,
            "baseline_count": total - enriched,
            "coverage_not_quality_score": True,
        }

    def list_profiles(self, *, status: str | None = None) -> list[dict]:
        rows = [self.profile(code) for code in sorted(self._names)]
        values = [row for row in rows if row is not None]
        if status:
            values = [row for row in values if row.get("profile_status") == status]
        return values
