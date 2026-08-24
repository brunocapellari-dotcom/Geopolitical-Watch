from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .historical_corpus import HistoricalCorpus


class EmpiricalHistory:
    """Layered historical catalog for evaluation and learning.

    Curated project cases and research-coded UCDP episodes remain distinct. The
    combined view is for analysis/evaluation only and does not promote either
    layer to live-event evidence or human-gold labels.
    """

    def __init__(self, curated_cases: list[dict], ucdp_cases: list[dict]) -> None:
        self.curated_cases = [dict(row) for row in curated_cases]
        self.ucdp_cases = [dict(row) for row in ucdp_cases]

    @classmethod
    def from_files(
        cls,
        *,
        curated_path: str | Path = "config/geopolitics/historical_crises.json",
        supplement_path: str | Path = "config/geopolitics/historical_crises_v011.json",
        ucdp_path: str | Path = "generated/ucdp/historical_cases.json",
    ) -> "EmpiricalHistory":
        curated = HistoricalCorpus.from_json(curated_path, supplement_path)
        ucdp_file = Path(ucdp_path)
        if ucdp_file.exists():
            payload = json.loads(ucdp_file.read_text(encoding="utf-8"))
            ucdp_cases = list(payload.get("cases", []))
        else:
            ucdp_cases = []
        return cls(list(curated.cases.values()), ucdp_cases)

    def layered_cases(self) -> list[dict]:
        rows: list[dict] = []
        for case in self.curated_cases:
            rows.append({
                **case,
                "corpus_layer": "project_curated",
                "research_coded_dataset": False,
                "human_gold": bool(case.get("human_gold", False)),
                "live_event_evidence": False,
            })
        for case in self.ucdp_cases:
            rows.append({
                **case,
                "corpus_layer": "ucdp_research_coded",
                "research_coded_dataset": True,
                "human_gold": False,
                "live_event_evidence": False,
            })
        return sorted(rows, key=lambda row: (str(row.get("start") or ""), str(row.get("case_id") or "")))

    def as_of(self, cutoff: str) -> list[dict]:
        rows: list[dict] = []
        for case in self.layered_cases():
            start = str(case.get("start") or "")
            if not start or start > cutoff:
                continue
            row = dict(case)
            end = str(case.get("end") or "")
            if not end or end > cutoff:
                row["outcome_tags"] = []
                row["outcome_hidden_due_to_cutoff"] = True
            else:
                row["outcome_hidden_due_to_cutoff"] = False
            rows.append(row)
        return rows

    def summary(self) -> dict:
        layered = self.layered_cases()
        years = [int(str(row["start"])[:4]) for row in layered if str(row.get("start") or "")[:4].isdigit()]
        outcomes = Counter(tag for row in layered for tag in row.get("outcome_tags", []))
        regions = Counter(str(row.get("region") or "Unknown") for row in layered)
        human_gold_count = sum(1 for row in layered if row.get("human_gold"))
        source_backed = sum(1 for row in layered if row.get("source_ids"))
        return {
            "schema_version": "geowatch-empirical-history-summary-v1",
            "total_case_count": len(layered),
            "project_curated_count": len(self.curated_cases),
            "ucdp_research_coded_count": len(self.ucdp_cases),
            "source_backed_count": source_backed,
            "human_gold_count": human_gold_count,
            "historical_year_min": min(years) if years else None,
            "historical_year_max": max(years) if years else None,
            "outcome_tag_counts": dict(sorted(outcomes.items())),
            "region_counts": dict(sorted(regions.items())),
            "layers_remain_distinct": True,
            "research_coded_history_is_not_live_event_confirmation": True,
            "research_coded_history_is_not_human_gold": True,
        }

    def evaluation_windows(self, *, min_history_years: int = 10) -> list[dict]:
        years = sorted({int(str(row["start"])[:4]) for row in self.layered_cases() if str(row.get("start") or "")[:4].isdigit()})
        if not years:
            return []
        first_test = min(years) + max(1, min_history_years)
        return [
            {
                "train_through": f"{year - 1}-12-31",
                "test_start": f"{year}-01-01",
                "test_end": f"{year}-12-31",
                "strict_temporal_split": True,
            }
            for year in years
            if year >= first_test
        ]
