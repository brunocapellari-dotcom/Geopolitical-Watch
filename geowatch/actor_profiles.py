from __future__ import annotations

import json
from pathlib import Path


class ActorProfiles:
    def __init__(self,payload:dict)->None:
        self.payload=payload; self.profiles={row["actor_id"]:row for row in payload.get("profiles",[])}

    @classmethod
    def from_json(cls,path: str|Path="config/geopolitics/actor_profiles.json") -> "ActorProfiles":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def profile(self,actor_id:str)->dict|None:
        row=self.profiles.get(actor_id)
        return {**row,"context_not_evidence":True} if row else None

    def list(self,actor_type:str|None=None)->list[dict]:
        rows=[{**row,"context_not_evidence":True} for row in self.profiles.values()]
        if actor_type: rows=[row for row in rows if row.get("actor_type")==actor_type]
        return sorted(rows,key=lambda row:row["name"])
