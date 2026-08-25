from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


class ActorProfiles:
    def __init__(self,payload:dict)->None:
        self.payload=payload; self.profiles={row["actor_id"]:row for row in payload.get("profiles",[])}

    @classmethod
    def from_json(cls,path: str|Path="config/geopolitics/actor_profiles.json", supplemental_paths: Iterable[str|Path]=("config/geopolitics/actor_profiles_v013.json",)) -> "ActorProfiles":
        base=json.loads(Path(path).read_text(encoding="utf-8")); profiles=list(base.get("profiles",[]))
        for supplement_path in supplemental_paths:
            p=Path(supplement_path)
            if not p.exists(): continue
            extra=json.loads(p.read_text(encoding="utf-8")); existing={row["actor_id"] for row in profiles}
            profiles.extend(row for row in extra.get("profiles",[]) if row["actor_id"] not in existing)
        return cls({**base,"profiles":profiles})

    def profile(self,actor_id:str)->dict|None:
        row=self.profiles.get(actor_id); return {**row,"context_not_evidence":True} if row else None

    def list(self,actor_type:str|None=None)->list[dict]:
        rows=[{**row,"context_not_evidence":True} for row in self.profiles.values()]
        if actor_type: rows=[row for row in rows if row.get("actor_type")==actor_type]
        return sorted(rows,key=lambda row:row["name"])

    def coverage(self)->dict:
        return {"schema_version":"geowatch-actor-profile-coverage-v1","profile_count":len(self.profiles),"system_reviewed_structural_count":sum(1 for r in self.profiles.values() if r.get("source_ids")),"human_gold":False,"context_not_evidence":True}
