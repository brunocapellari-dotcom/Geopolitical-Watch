from __future__ import annotations

import json
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.knowledge_sync import build_obsidian_bundle,validate_obsidian_bundle


def load(path: str)->dict:
    p=Path(path); return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def main()->int:
    ucdp=load("generated/ucdp/summary.json")
    exposure=load("config/geopolitics/chokepoint_exposure_v014.json")
    source_catalog=load("config/geopolitics/strategic_data_sources_v014.json")
    obsidian=build_obsidian_bundle(); obsidian_validation=validate_obsidian_bundle(obsidian)
    checks=[
        {"id":"human_review_items_prepared_500","value":ucdp.get("human_review_items_prepared",0),"passed":int(ucdp.get("human_review_items_prepared") or 0)>=500},
        {"id":"human_review_batches_5","value":ucdp.get("human_review_batch_count",0),"passed":int(ucdp.get("human_review_batch_count") or 0)>=5},
        {"id":"chokepoint_exposures_5","value":len(exposure.get("observations",[])),"passed":len(exposure.get("observations",[]))>=5},
        {"id":"strategic_source_catalog_8","value":len(source_catalog.get("sources",[])),"passed":len(source_catalog.get("sources",[]))>=8},
        {"id":"obsidian_notes_6","value":obsidian.get("note_count",0),"passed":obsidian.get("note_count",0)>=6 and obsidian_validation["passed"]},
    ]
    payload={
        "schema_version":"geowatch-v014-operational-learning-gate-v1","checks":checks,"passed":all(r["passed"] for r in checks),
        "human_gold_completed":int(ucdp.get("human_gold_completed_count") or 0),
        "human_gold_not_fabricated":int(ucdp.get("human_gold_completed_count") or 0)==0,
        "prospective_track_record_requires_future_resolution":True,
        "production_gcp_gate_external":True,
        "obsidian_bundle":obsidian,
        "limitations":[
            "Prepared review items are not human-gold until explicitly reviewed.",
            "Source catalog registration does not imply every planned source is activated.",
            "Chokepoint baselines are dated exposure observations, not disruption probabilities.",
            "Production/restore/security/cost gates require external execution evidence."
        ]
    }
    out=Path("generated/v014"); out.mkdir(parents=True,exist_ok=True); (out/"operational_learning.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False,indent=2)); return 0 if payload["passed"] else 1


if __name__=="__main__": raise SystemExit(main())
