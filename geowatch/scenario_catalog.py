from __future__ import annotations

import json
from pathlib import Path


class ScenarioCatalog:
    def __init__(self,payload:dict)->None:
        self.payload=payload; self.scenarios={row["scenario_id"]:row for row in payload.get("scenarios",[])}

    @classmethod
    def from_json(cls,path: str|Path="config/geopolitics/chokepoint_scenarios_v013.json") -> "ScenarioCatalog":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def get(self,scenario_id:str)->dict|None:
        row=self.scenarios.get(scenario_id)
        return {**row,"structural_scenario_not_forecast":True} if row else None

    def list(self)->list[dict]:
        return [{**row,"structural_scenario_not_forecast":True} for row in self.scenarios.values()]

    def summary(self)->dict:
        return {"schema_version":"geowatch-scenario-catalog-summary-v1","scenario_count":len(self.scenarios),"scenario_ids":sorted(self.scenarios),"route_share_inputs_required":True,"scenario_is_not_forecast":True}
