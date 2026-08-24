from __future__ import annotations

import json
from datetime import date
from pathlib import Path


class HistoricalCorpus:
    def __init__(self,payload: dict)->None:
        self.payload=payload; self.cases={row["case_id"]:row for row in payload.get("cases",[])}

    @classmethod
    def from_json(cls,path: str|Path="config/geopolitics/historical_crises.json") -> "HistoricalCorpus":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def as_of(self,cutoff: str) -> list[dict]:
        """Return only case information knowable by cutoff; outcome tags are hidden for active cases."""
        rows=[]
        for case in self.cases.values():
            if case["start"]>cutoff: continue
            row={k:v for k,v in case.items() if k!="outcome_tags"}
            end=case.get("end")
            row["outcome_tags"] = list(case.get("outcome_tags",[])) if end and end<=cutoff else []
            row["outcome_hidden_due_to_cutoff"] = not bool(end and end<=cutoff)
            rows.append(row)
        return sorted(rows,key=lambda r:r["start"])

    def summary(self)->dict:
        regions={}; types={}
        for case in self.cases.values():
            regions[case["region"]]=regions.get(case["region"],0)+1
            for kind in case.get("types",[]): types[kind]=types.get(kind,0)+1
        return {"schema_version":"geowatch-historical-corpus-summary-v1","case_count":len(self.cases),"regions":dict(sorted(regions.items())),"types":dict(sorted(types.items())),"corpus_quality":"seed_requires_source_enrichment"}

    def evaluation_windows(self,*,min_history_years:int=5)->list[dict]:
        years=sorted({int(c["start"][:4]) for c in self.cases.values()})
        if not years: return []
        start=min(years)+min_history_years
        return [{"train_through":f"{year-1}-12-31","test_start":f"{year}-01-01","test_end":f"{year}-12-31"} for year in years if year>=start]
