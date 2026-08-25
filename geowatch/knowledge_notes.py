from __future__ import annotations

from datetime import datetime,timezone


def render_release_note(*, version: str, merged_sha: str | None, summary: list[str], limitations: list[str], evidence: list[str]) -> str:
    now=datetime.now(timezone.utc).date().isoformat()
    lines=["---",f"title: Release {version}","project: Monitor de Conflitos",f"updated: {now}","knowledge_status: canonical","---","",f"# Release {version}","",f"Merge SHA: `{merged_sha or 'PENDING'}`","","## Mudanças"]
    lines.extend(f"- {x}" for x in summary); lines.extend(["","## Evidências"]); lines.extend(f"- {x}" for x in evidence); lines.extend(["","## Limitações"]); lines.extend(f"- {x}" for x in limitations)
    lines.extend(["","[[MOC_Monitor_de_Conflitos]]",""])
    return "\n".join(lines)


def render_incident_note(incident: dict) -> str:
    iid=str(incident.get("incident_id") or "unknown"); detected=str(incident.get("detected_at") or "unknown")
    lines=["---",f"title: Incident {iid}","project: Monitor de Conflitos",f"updated: {detected[:10]}","knowledge_status: incident_evidence","---","",f"# Incident {iid}","",f"- Type: {incident.get('incident_type')}",f"- Severity: {incident.get('severity')}",f"- Detected: {detected}",f"- Expected: {incident.get('expected_behavior')}",f"- Observed: {incident.get('observed_behavior')}",f"- Root cause: {incident.get('root_cause') or 'OPEN'}","","## Evidência"]
    for row in incident.get("evidence",[]): lines.append(f"- `{row}`")
    lines.extend(["","## Governança","- Resultado negativo preservado.","- Incidente não altera modelo/threshold automaticamente.","","[[Operacao_Beta_SLO_Incidentes_e_MTTR]]",""])
    return "\n".join(lines)
