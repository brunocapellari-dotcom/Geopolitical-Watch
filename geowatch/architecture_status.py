from __future__ import annotations

import json
from pathlib import Path

from .ai_roles import load_ai_roles
from .source_registry import load_registry


def build_architecture_status(
    *,
    audit_path: str | Path = "config/architecture_audit.json",
    source_registry_path: str | Path = "config/source_registry.json",
    ai_roles_path: str | Path = "config/ai_roles.json",
) -> dict[str, object]:
    audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
    sources = load_registry(source_registry_path)
    roles = load_ai_roles(ai_roles_path)
    return {
        "schema_version": "geowatch-architecture-status-v1",
        "as_of": audit.get("as_of"),
        "source_registry": sources.summary(),
        "ai_roles": roles.summary(),
        "audit": {
            "domains": audit.get("domains", []),
            "release_gate": audit.get("release_gate", {}),
        },
        "canonical_verdicts": [
            "CONFIRMADO",
            "PROVÁVEL",
            "NÃO VERIFICADO",
            "CONFLITANTE",
            "FALSO",
        ],
        "operational_event_fields": [
            "what",
            "where",
            "when",
            "who",
            "source",
            "evidence",
            "confidence",
            "status",
        ],
        "security": {
            "external_content_trust": "untrusted",
            "commands_from_source_content": "forbidden",
            "hostile_interactive_content_requires_isolation": True,
            "historical_raw_evidence_immutable": True,
        },
    }
