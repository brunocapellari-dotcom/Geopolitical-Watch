from __future__ import annotations

import json
from pathlib import Path

from .global_profiles import GlobalProfileRegistry


class ProfileEnrichmentQueue:
    def __init__(self, priorities: dict, registry: GlobalProfileRegistry) -> None:
        self.priorities=priorities; self.registry=registry

    @classmethod
    def from_files(cls, priorities_path: str|Path="config/geopolitics/profile_priorities.json") -> "ProfileEnrichmentQueue":
        return cls(json.loads(Path(priorities_path).read_text(encoding="utf-8")),GlobalProfileRegistry.from_files())

    def queue(self, *, limit:int=100)->list[dict]:
        rows=[]
        for tier in self.priorities.get("tiers",[]):
            for code in tier.get("countries",[]):
                profile=self.registry.profile(code)
                if not profile: continue
                enriched=profile.get("profile_status")=="enriched"
                if not enriched:
                    rows.append({"country_id":code,"tier":tier["tier"],"status":"needs_enrichment","rationale":tier.get("rationale")})
        return sorted(rows,key=lambda r:(r["tier"],r["country_id"]))[:limit]

    def progress(self)->dict:
        values=[]
        for tier in self.priorities.get("tiers",[]):
            countries=tier.get("countries",[]); enriched=0
            for code in countries:
                p=self.registry.profile(code)
                enriched += bool(p and p.get("profile_status")=="enriched")
            total=len(countries)
            values.append({"tier":tier["tier"],"total":total,"enriched":enriched,"ratio":round(enriched/total,4) if total else 0.0})
        return {"schema_version":"geowatch-profile-enrichment-progress-v1","tiers":values,"queue_size":len(self.queue(limit=10000)),"coverage_not_quality_score":True}
