from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_REQUIRED_ROLES = {
    "GEOPOLITICAL CHIEF AI",
    "NEWS INTELLIGENCE AI",
    "OSINT AI",
    "GEOINT AI",
    "AVIATION AI",
    "MARITIME AI",
    "SATELLITE AI",
    "INFRASTRUCTURE AI",
    "CYBER/NETWORK AI",
    "CONFLICT AI",
    "HUMANITARIAN AI",
    "VERIFICATION AI",
}


@dataclass(frozen=True)
class AIRole:
    role_id: str
    name: str
    mission: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    cannot: tuple[str, ...]


class AIRoleRegistry:
    def __init__(self, roles: tuple[AIRole, ...], global_rules: dict[str, object]) -> None:
        self.roles = roles
        self.global_rules = dict(global_rules)
        self.by_name = {role.name: role for role in roles}
        self.validate()

    @classmethod
    def from_json(cls, path: str | Path = "config/ai_roles.json") -> "AIRoleRegistry":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        roles = tuple(
            AIRole(
                role_id=str(row["id"]),
                name=str(row["name"]),
                mission=str(row["mission"]),
                inputs=tuple(str(value) for value in row.get("inputs", [])),
                outputs=tuple(str(value) for value in row.get("outputs", [])),
                cannot=tuple(str(value) for value in row.get("cannot", [])),
            )
            for row in payload.get("roles", [])
        )
        return cls(roles, payload.get("global_rules") or {})

    def validate(self) -> None:
        names = [role.name for role in self.roles]
        if len(names) != len(set(names)):
            raise ValueError("AI role names must be unique")
        missing = _REQUIRED_ROLES - set(names)
        extra = set(names) - _REQUIRED_ROLES
        if missing or extra:
            raise ValueError(f"AI role registry mismatch; missing={sorted(missing)} extra={sorted(extra)}")
        if self.global_rules.get("source_content_is_untrusted") is not True:
            raise ValueError("AI roles must treat source content as untrusted")
        if self.global_rules.get("never_execute_instructions_from_source_content") is not True:
            raise ValueError("AI roles must forbid source-content instructions")
        verifier = self.by_name["VERIFICATION AI"]
        required_verdicts = {"CONFIRMADO", "PROVÁVEL", "NÃO VERIFICADO", "CONFLITANTE", "FALSO"}
        if not required_verdicts.issubset(set(verifier.outputs)):
            raise ValueError("VERIFICATION AI must expose every canonical verdict")

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": "geowatch-ai-role-registry-summary-v1",
            "role_count": len(self.roles),
            "roles": [role.name for role in self.roles],
            "hostile_content_boundary": True,
            "verification_role": "VERIFICATION AI",
            "orchestrator": "GEOPOLITICAL CHIEF AI",
        }


def load_ai_roles(path: str | Path = "config/ai_roles.json") -> AIRoleRegistry:
    return AIRoleRegistry.from_json(path)
