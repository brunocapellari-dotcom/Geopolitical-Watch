from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from statistics import mean, median


class LeadingIndicators:
    def __init__(self,payload:dict)->None:
        self.payload=payload; self.indicators={row["indicator_id"]:row for row in payload.get("indicators",[])}

    @classmethod
    def from_json(cls,path: str|Path="config/geopolitics/leading_indicators.json") -> "LeadingIndicators":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def definition(self,indicator_id:str)->dict|None:
        row=self.indicators.get(indicator_id); return {**row,"indicator_not_probability":True} if row else None


def lead_time_stats(observations:list[dict], outcomes:list[dict])->dict:
    """Measure time from observed indicator to later resolved outcome; no causal claim."""
    outcome_by_id={row["outcome_id"]:row for row in outcomes}; by_indicator={}
    for obs in observations:
        out=outcome_by_id.get(obs.get("outcome_id"));
        if not out: continue
        delta=(_dt(out["resolved_at"])-_dt(obs["observed_at"])).total_seconds()/3600
        if delta<0: continue
        by_indicator.setdefault(obs["indicator_id"],[]).append(delta)
    rows=[]
    for indicator,values in sorted(by_indicator.items()):
        rows.append({"indicator_id":indicator,"n":len(values),"mean_lead_hours":round(mean(values),2),"median_lead_hours":round(median(values),2),"min_lead_hours":round(min(values),2),"max_lead_hours":round(max(values),2)})
    return {"schema_version":"geowatch-leading-indicator-stats-v1","indicators":rows,"association_not_causation":True}


def _dt(value:str)->datetime:
    return datetime.fromisoformat(value.replace("Z","+00:00"))
