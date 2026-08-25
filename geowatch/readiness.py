from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping


class ReadinessModel:
    def __init__(self,payload:dict)->None: self.payload=payload

    @classmethod
    def from_json(cls,path: str|Path="config/readiness.json") -> "ReadinessModel": return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def evaluate(self,dimension_scores:Mapping[str,float],hard_gates:Mapping[str,bool])->dict:
        weighted=0.0; dimensions=[]
        for row in self.payload.get("dimensions",[]):
            score=max(0.0,min(1.0,float(dimension_scores.get(row["id"],0.0)))); component=score*float(row["weight"]); weighted+=component
            dimensions.append({**row,"score":round(score,4),"weighted":round(component,4)})
        gates=[{"gate":gate,"passed":bool(hard_gates.get(gate,False))} for gate in self.payload.get("hard_gates",[])]
        target=float(self.payload.get("target",0.95)); all_gates=all(row["passed"] for row in gates)
        return {"schema_version":"geowatch-readiness-result-v1","weighted_readiness":round(weighted,4),"target":target,"hard_gates":gates,"all_hard_gates_passed":all_gates,"target_reached":weighted>=target and all_gates,"dimensions":dimensions,"readiness_not_accuracy":True}

    def missing_for_target(self,result:dict)->dict:
        return {"failed_gates":[r["gate"] for r in result.get("hard_gates",[]) if not r["passed"]],"weak_dimensions":[r["id"] for r in result.get("dimensions",[]) if float(r["score"])<0.9],"weighted_gap":round(max(0.0,float(result["target"])-float(result["weighted_readiness"])),4)}


def current_code_readiness_estimate()->dict:
    """Conservative v0.13 project-state estimate. It is not an accuracy score."""
    scores={
      "core_architecture":0.99,"evidence_governance":0.99,"source_coverage":0.80,"historical_coverage":0.94,
      "strategic_knowledge":0.96,"empirical_validation":0.80,"forecast_calibration":0.68,"production_operations":0.68,
      "security_source_rights":0.80,"documentation_recovery":0.98,
    }
    gates={
      "live_production_smoke_passed":False,"database_restore_drill_passed":False,"source_credentials_and_terms_reviewed":False,
      "historical_out_of_sample_validation_completed":False,"security_and_source_rights_audit_completed":False,
    }
    result=ReadinessModel.from_json().evaluate(scores,gates); result["estimate_type"]="conservative_v0.13_project_state_estimate"; result["assessed_at"]="2026-08-25"; return result
