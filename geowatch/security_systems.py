from __future__ import annotations

import json
from pathlib import Path


class SecuritySystems:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.systems = {row["system_id"]: row for row in payload.get("systems", [])}

    @classmethod
    def from_json(cls, path: str | Path = "config/geopolitics/security_systems.json") -> "SecuritySystems":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def memberships(self, country_code: str) -> list[dict]:
        code = country_code.upper()
        return [
            {
                "system_id": row["system_id"],
                "name": row["name"],
                "relationship_type": row["relationship_type"],
                "source_url": row.get("source_url"),
                "valid_from": row.get("valid_from"),
                "valid_to": row.get("valid_to"),
                "notes": row.get("notes", []),
                "context_not_evidence": True,
            }
            for row in self.systems.values() if code in row.get("member_codes", [])
        ]

    def pair_context(self, left: str, right: str) -> dict:
        left, right = left.upper(), right.upper()
        shared = []
        for row in self.systems.values():
            members = set(row.get("member_codes", []))
            if {left, right} <= members:
                shared.append({"system_id": row["system_id"], "relationship_type": row["relationship_type"], "source_url": row.get("source_url")})
        return {
            "left": left,
            "right": right,
            "shared_systems": shared,
            "context_not_evidence": True,
            "methodology_notes": ["Shared membership does not imply identical interests or automatic future action."]
        }
