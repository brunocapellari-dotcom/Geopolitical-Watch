from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


def build_obsidian_bundle(source_dir: str|Path="knowledge/obsidian/monitor_conflitos", output_dir: str|Path="generated/obsidian/monitor_conflitos") -> dict:
    src=Path(source_dir); out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    notes=[]
    for path in sorted(src.glob("*.md")):
        payload=path.read_bytes(); digest=hashlib.sha256(payload).hexdigest(); target=out/path.name
        shutil.copyfile(path,target)
        text=payload.decode("utf-8",errors="replace")
        notes.append({"file":path.name,"sha256":digest,"bytes":len(payload),"wikilinks":text.count("[["),"has_frontmatter":text.startswith("---\n")})
    manifest={
        "schema_version":"geowatch-obsidian-bundle-v1","project":"Monitor de Conflitos / Geopolitical Watch",
        "note_count":len(notes),"notes":notes,"source_dir":str(src),"output_dir":str(out),
        "github_is_code_truth":True,"obsidian_is_knowledge_interface":True,
        "negative_results_must_be_preserved":True,"material_claims_require_evidence_and_source":True,
    }
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest


def validate_obsidian_bundle(manifest: dict) -> dict:
    issues=[]
    if manifest.get("note_count",0)<5: issues.append("too_few_canonical_notes")
    for row in manifest.get("notes",[]):
        if not row.get("has_frontmatter"): issues.append(f"missing_frontmatter:{row.get('file')}")
    return {"schema_version":"geowatch-obsidian-bundle-validation-v1","passed":not issues,"issues":issues,"note_count":manifest.get("note_count",0)}
