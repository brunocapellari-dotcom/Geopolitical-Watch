from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable


def release_note(*, version: str, merge_commit: str, released_at: str, gates: Iterable[dict], capabilities: Iterable[str], hard_gates_open: Iterable[str]) -> str:
    gate_rows="\n".join(f"- {g.get('name') or g.get('id')}: {g.get('conclusion') or g.get('status') or ('passed' if g.get('passed') else 'failed')}" for g in gates)
    caps="\n".join(f"- {x}" for x in capabilities); hard="\n".join(f"- {x}" for x in hard_gates_open)
    return f"""---
title: Release v{version}
project: Monitor de Conflitos
updated: {released_at[:10]}
knowledge_status: canonical
release: {version}
merge_commit: {merge_commit}
---

# Release v{version}

## Gates
{gate_rows or '- no gate metadata supplied'}

## Capacidades
{caps or '- none recorded'}

## Hard gates ainda abertos
{hard or '- none recorded'}

## Regra
Release note registra o que foi comprovado. Ausência de evidência nunca é convertida em conclusão positiva.

[[MOC_Monitor_de_Conflitos]]
"""


def incident_note(incident: dict) -> str:
    iid=str(incident.get("incident_id") or "unknown"); observed=str(incident.get("detected_at") or incident.get("observed_at") or "")
    evidence="\n".join(f"- {json.dumps(x,ensure_ascii=False,sort_keys=True)}" for x in incident.get("evidence",[])) or "- none"
    return f"""---
title: Incident {iid}
project: Monitor de Conflitos
updated: {observed[:10]}
knowledge_status: evidence
incident_id: {iid}
---

# Incident {iid}

- Type: {incident.get('incident_type') or incident.get('type')}
- Severity: {incident.get('severity')}
- Detected: {observed}
- Status: {incident.get('status','open')}

## Expected
{incident.get('expected_behavior','')}

## Observed
{incident.get('observed_behavior','')}

## Evidence
{evidence}

## Root cause
{incident.get('root_cause') or 'not yet established'}

[[Operacao_Beta_SLO_Incidentes_e_MTTR]]
"""


def write_release_note(*, root: str|Path, version: str, merge_commit: str, released_at: str, gates: Iterable[dict], capabilities: Iterable[str], hard_gates_open: Iterable[str]) -> Path:
    path=Path(root)/f"Release_v{version}.md"; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(release_note(version=version,merge_commit=merge_commit,released_at=released_at,gates=gates,capabilities=capabilities,hard_gates_open=hard_gates_open),encoding="utf-8"); return path


def write_incident_notes(incidents: Iterable[dict], *, root: str|Path) -> list[Path]:
    out=[]; base=Path(root); base.mkdir(parents=True,exist_ok=True)
    for row in incidents:
        iid=str(row.get("incident_id") or hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()[:16]); path=base/f"Incident_{iid}.md"; path.write_text(incident_note({**row,"incident_id":iid}),encoding="utf-8"); out.append(path)
    return out


def compare_knowledge_manifests(expected: dict, mirror: dict) -> dict:
    exp={r.get("file"):r.get("sha256") for r in expected.get("notes",[])}; got={r.get("file"):r.get("sha256") for r in mirror.get("notes",[])}
    missing=sorted(set(exp)-set(got)); extra=sorted(set(got)-set(exp)); changed=sorted(name for name in set(exp)&set(got) if exp[name]!=got[name])
    return {"schema_version":"geowatch-knowledge-drift-v1","missing":missing,"extra":extra,"changed":changed,"drift":bool(missing or extra or changed),"expected_count":len(exp),"mirror_count":len(got)}
