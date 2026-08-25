from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


class GlobalProfileRegistry:
    """Global country/territory coverage without pretending full enrichment."""

    def __init__(self, registry: dict, enriched: dict) -> None:
        self.registry=registry; self.enriched=enriched
        self._names={code:name for code,name in registry.get("countries",[])}
        self._profiles={row["country_id"]:row for row in enriched.get("profiles",[])}

    @classmethod
    def from_files(cls, registry_path: str|Path="config/geopolitics/country_registry.json",
                   enriched_path: str|Path="config/geopolitics/country_profiles.json",
                   supplemental_paths: Iterable[str|Path]=("config/geopolitics/country_profiles_v011.json","config/geopolitics/country_profiles_v013.json")) -> "GlobalProfileRegistry":
        base=json.loads(Path(enriched_path).read_text(encoding="utf-8")); profiles=list(base.get("profiles",[]))
        for path in supplemental_paths:
            p=Path(path)
            if not p.exists(): continue
            supplement=json.loads(p.read_text(encoding="utf-8")); existing={row["country_id"] for row in profiles}
            profiles.extend(row for row in supplement.get("profiles",[]) if row["country_id"] not in existing)
        return cls(json.loads(Path(registry_path).read_text(encoding="utf-8")),{**base,"profiles":profiles})

    def profile(self,country_id:str)->dict|None:
        code=country_id.upper()
        if code not in self._names: return None
        if code in self._profiles: return {**self._profiles[code],"profile_status":"enriched","context_not_evidence":True}
        return {"country_id":code,"name":self._names[code],"profile_status":"baseline_needs_enrichment","context_not_evidence":True,"strategic_themes":[],"exposures":[],"questions":["Which structural interests, dependencies, alliances and vulnerabilities require sourced enrichment?"],"source_ids":[]}

    def coverage(self)->dict:
        total=len(self._names); enriched=len(set(self._profiles)&set(self._names))
        return {"schema_version":"geowatch-country-profile-coverage-v1","registry_count":total,"enriched_count":enriched,"enrichment_ratio":round(enriched/total,4) if total else 0.0,"baseline_count":total-enriched,"coverage_not_quality_score":True}

    def list_profiles(self,*,status:str|None=None)->list[dict]:
        values=[self.profile(code) for code in sorted(self._names)]; values=[row for row in values if row is not None]
        return [row for row in values if row.get("profile_status")==status] if status else values
