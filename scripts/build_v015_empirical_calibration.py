from __future__ import annotations

import json
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.knowledge_sync import build_obsidian_bundle,validate_obsidian_bundle


def load(path: str, default=None):
    p=Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else ({} if default is None else default)


def main()->int:
    wpi=load("generated/wpi/summary.json")
    unloc=load("generated/unlocode/global_summary.json")
    cross=load("generated/unlocode/global_wpi_crosswalk_summary.json")
    strategic=load("generated/strategic_sources/summary.json")
    review=load("generated/human_review/interface/summary.json")
    gold=load("generated/human_gold/gold_v1.json")
    obsidian=build_obsidian_bundle(); knowledge=validate_obsidian_bundle(obsidian)
    gold_count=int(((gold.get("progress") or {}).get("human_gold_count") or (gold.get("gold") or {}).get("count") or 0))
    checks=[
        {"id":"wpi_global_ports","value":int(wpi.get("normalized_port_count") or 0),"minimum":3000},
        {"id":"unlocode_global_rows","value":int(unloc.get("row_count") or 0),"minimum":10000},
        {"id":"wpi_unlocode_matches","value":int(cross.get("matched_count") or 0),"minimum":1000},
        {"id":"faostat_catalogs_reachable","value":int(strategic.get("faostat_catalog_successes") or 0),"minimum":4},
        {"id":"eia_bulk_international_entries","value":int((strategic.get("eia") or {}).get("international_bulk_entries") or 0),"minimum":1},
        {"id":"human_review_interface_items","value":int(review.get("item_count") or 0),"minimum":100},
        {"id":"obsidian_canonical_notes","value":int(obsidian.get("note_count") or 0),"minimum":9},
    ]
    for row in checks: row["passed"]=row["value"]>=row["minimum"]
    hard_gates={
        "human_gold_500":{"passed":gold_count>=500,"value":gold_count},
        "prospective_forecasts_resolved_200":{"passed":False,"value":"requires accumulated future outcomes"},
        "reviewed_critical_infrastructure_50":{"passed":False,"value":"requires multi-source strategic evidence beyond identity"},
        "production_gcp":{"passed":False,"value":"requires external GCP execution evidence"},
        "restore_pitr":{"passed":False,"value":"requires real restore evidence"},
        "security_cost_rights":{"passed":False,"value":"requires final external audit evidence"},
    }
    payload={
        "schema_version":"geowatch-v015-empirical-calibration-gate-v1","software_data_knowledge_gate_passed":all(r["passed"] for r in checks) and knowledge["passed"],
        "checks":checks,"human_gold_count":gold_count,"hard_gates":hard_gates,"v1_hard_gates_passed":all(r["passed"] for r in hard_gates.values()),
        "v1_release_allowed":False,
        "governance":[
            "A v0.15 software/data/knowledge gate may pass while v1 hard gates remain open.",
            "Prepared review interfaces are not human-gold.",
            "Open prospective forecasts are not resolved track record.",
            "WPI/UNLOCODE identity corroboration is not strategic criticality.",
            "External production gates cannot be closed by unit tests."
        ],
        "obsidian":obsidian,
    }
    out=Path("generated/v015"); out.mkdir(parents=True,exist_ok=True); (out/"empirical_calibration.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in payload.items() if k!="obsidian"},ensure_ascii=False,indent=2))
    return 0 if payload["software_data_knowledge_gate_passed"] else 2

if __name__=="__main__": raise SystemExit(main())
