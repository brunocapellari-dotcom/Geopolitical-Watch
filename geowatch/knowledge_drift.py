from __future__ import annotations

from typing import Iterable


def compare_knowledge_manifests(github_manifest: dict, drive_manifest: dict) -> dict:
    gh={r.get("file"):r for r in github_manifest.get("notes",[]) if r.get("file")}
    dr={r.get("file"):r for r in drive_manifest.get("notes",[]) if r.get("file")}
    missing_drive=sorted(set(gh)-set(dr)); extra_drive=sorted(set(dr)-set(gh)); changed=[]
    for name in sorted(set(gh)&set(dr)):
        gsha=gh[name].get("sha256"); dsha=dr[name].get("sha256")
        if gsha and dsha and gsha!=dsha: changed.append({"file":name,"github_sha256":gsha,"drive_sha256":dsha})
    return {
        "schema_version":"geowatch-knowledge-drift-v1","github_note_count":len(gh),"drive_note_count":len(dr),
        "missing_in_drive":missing_drive,"extra_in_drive":extra_drive,"content_mismatch":changed,
        "drift_detected":bool(missing_drive or changed),"drive_extras_are_not_auto_deleted":True,
    }


def release_knowledge_gate(release_version: str, github_manifest: dict, drive_manifest: dict, required_notes: Iterable[str]) -> dict:
    drift=compare_knowledge_manifests(github_manifest,drive_manifest); drive_files={r.get("file") for r in drive_manifest.get("notes",[])}
    missing_required=sorted(set(required_notes)-drive_files)
    return {"schema_version":"geowatch-release-knowledge-gate-v1","release_version":release_version,"passed":not drift["drift_detected"] and not missing_required,"drift":drift,"missing_required_notes":missing_required,"knowledge_sync_is_part_of_release_definition":True}
