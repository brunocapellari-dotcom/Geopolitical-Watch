from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping


class ReleaseAudit:
    def __init__(self, rights: dict) -> None:
        self.rights = rights

    @classmethod
    def from_files(cls, rights_path: str | Path = "config/audit/source_rights.json") -> "ReleaseAudit":
        return cls(json.loads(Path(rights_path).read_text(encoding="utf-8")))

    def source_rights(self, enabled_sources: set[str]) -> dict:
        rows = [row for row in self.rights.get("sources", []) if row["source_id"] in enabled_sources]
        blocked = [row["source_id"] for row in rows if str(row.get("status", "")).startswith("pending")]
        return {
            "reviewed_enabled_sources": sorted(row["source_id"] for row in rows if row["source_id"] not in blocked),
            "blocked_enabled_sources": sorted(blocked),
            "passed": not blocked,
        }

    def evaluate(self, *, enabled_sources: set[str], evidence: Mapping[str, bool]) -> dict:
        rights = self.source_rights(enabled_sources)
        required = {
            "production_smoke": bool(evidence.get("production_smoke")),
            "restore_drill": bool(evidence.get("restore_drill")),
            "historical_oos": bool(evidence.get("historical_oos")),
            "security_review": bool(evidence.get("security_review")),
            "cost_review": bool(evidence.get("cost_review")),
            "source_rights": rights["passed"],
        }
        return {
            "schema_version": "geowatch-v1-release-audit-v1",
            "gates": required,
            "source_rights": rights,
            "passed": all(required.values()),
            "release_candidate_only_if_passed": True,
            "evidence_required_not_self_attestation": True,
        }
