from __future__ import annotations

import argparse,json
from pathlib import Path

from _repo_path import ensure_repo_path
ensure_repo_path()

from geowatch.knowledge_release import compare_knowledge_manifests
from geowatch.knowledge_sync import build_obsidian_bundle


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--mirror-manifest",default="state/obsidian_drive_manifest.json"); p.add_argument("--out",default="reports/knowledge_drift.json"); p.add_argument("--allow-missing-mirror",action="store_true"); args=p.parse_args()
    expected=build_obsidian_bundle(); mirror_path=Path(args.mirror_manifest)
    if not mirror_path.exists():
        payload={"schema_version":"geowatch-knowledge-drift-v1","status":"mirror_manifest_missing","drift":None,"expected_count":expected.get("note_count",0),"mirror_count":None,"external_drive_sync_evidence_required":True}
        Path(args.out).parent.mkdir(parents=True,exist_ok=True); Path(args.out).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(payload,ensure_ascii=False,indent=2)); return 0 if args.allow_missing_mirror else 2
    mirror=json.loads(mirror_path.read_text(encoding="utf-8")); payload=compare_knowledge_manifests(expected,mirror); payload["status"]="drift" if payload["drift"] else "in_sync"; payload["external_drive_sync_evidence_required"]=True
    Path(args.out).parent.mkdir(parents=True,exist_ok=True); Path(args.out).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(payload,ensure_ascii=False,indent=2)); return 2 if payload["drift"] else 0

if __name__=="__main__": raise SystemExit(main())
