from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping


class ForecastTemplates:
    def __init__(self, payload: dict) -> None:
        self.payload=payload; self.templates={row["template_id"]:row for row in payload.get("templates",[])}

    @classmethod
    def from_json(cls,path: str|Path="config/geopolitics/forecast_templates.json") -> "ForecastTemplates":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def template(self,template_id: str) -> dict:
        if template_id not in self.templates: raise KeyError(template_id)
        return self.templates[template_id]

    def instantiate(self,template_id: str,*,episode_id: str,created_at: str,probabilities: Mapping[int,float]) -> list[dict]:
        row=self.template(template_id); start=_dt(created_at); result=[]
        for days in row.get("horizons_days",[]):
            probability=float(probabilities[days])
            if not 0<=probability<=1: raise ValueError("probability must be in [0,1]")
            horizon=(start+timedelta(days=int(days))).isoformat()
            result.append({
                "template_id":template_id,"episode_id":episode_id,"created_at":start.isoformat(),"horizon_at":horizon,"horizon_days":int(days),
                "question":row["question"].format(episode_id=episode_id,horizon=horizon),"resolution_rule":row["outcome_rule"],"probability":probability,
                "probability_not_evidence":True,
            })
        return result


def monotonicity_flags(rows: list[dict]) -> list[str]:
    """Diagnostic only: some cumulative event questions should usually be non-decreasing by horizon."""
    ordered=sorted(rows,key=lambda r:int(r.get("horizon_days",0))); flags=[]
    for left,right in zip(ordered,ordered[1:]):
        if float(right["probability"])+1e-9<float(left["probability"]): flags.append(f"probability_decreases:{left['horizon_days']}->{right['horizon_days']}")
    return flags


def _dt(value: str) -> datetime:
    dt=datetime.fromisoformat(value.replace("Z","+00:00")); return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
