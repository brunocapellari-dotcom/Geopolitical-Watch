from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


_ALLOWED_AI_ROLES = {
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
_HOSTILE_TRUST = {"hostile_untrusted"}
_DELEGATED_RUNTIME_MODES = {
    "reference_only",
    "registry_family",
    "pull_on_view",
    "continuous_stream",
    "runtime_on_demand",
}


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    name: str
    domain: str
    owner_ai: str
    runtime_mode: str
    cadence_seconds: int
    activation: str
    implementation: str
    credential_env: tuple[str, ...]
    credential_options: tuple[tuple[str, ...], ...]
    terms_gate: bool
    evidence_role: str
    content_trust: str
    browser_isolation: bool
    backfill: bool = False
    url: str | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, row: dict[str, object]) -> "SourceSpec":
        return cls(
            source_id=str(row["source_id"]),
            name=str(row["name"]),
            domain=str(row["domain"]),
            owner_ai=str(row["owner_ai"]),
            runtime_mode=str(row["runtime_mode"]),
            cadence_seconds=int(row["cadence_seconds"]),
            activation=str(row["activation"]),
            implementation=str(row["implementation"]),
            credential_env=tuple(str(value) for value in (row.get("credential_env") or [])),
            credential_options=tuple(
                tuple(str(value) for value in option)
                for option in (row.get("credential_options") or [])
            ),
            terms_gate=bool(row.get("terms_gate", False)),
            evidence_role=str(row["evidence_role"]),
            content_trust=str(row["content_trust"]),
            browser_isolation=bool(row.get("browser_isolation", False)),
            backfill=bool(row.get("backfill", False)),
            url=str(row["url"]) if row.get("url") else None,
            notes=str(row["notes"]) if row.get("notes") else None,
        )

    def credentials_ready(self) -> bool:
        if self.credential_options:
            return any(all(os.environ.get(name, "").strip() for name in option) for option in self.credential_options)
        return all(os.environ.get(name, "").strip() for name in self.credential_env)

    def missing_credentials(self) -> tuple[str, ...]:
        if self.credentials_ready():
            return ()
        if self.credential_options:
            missing_options = [
                tuple(name for name in option if not os.environ.get(name, "").strip())
                for option in self.credential_options
            ]
            best = min(missing_options, key=lambda values: (len(values), values))
            return best
        return tuple(name for name in self.credential_env if not os.environ.get(name, "").strip())

    @property
    def implemented(self) -> bool:
        return self.implementation not in {"not_implemented", "source_specific_registration_required"}

    @property
    def can_run(self) -> bool:
        return self.implemented and self.activation.startswith("active") and self.credentials_ready()


class SourceRegistry:
    def __init__(self, specs: Iterable[SourceSpec], *, governance: dict[str, object] | None = None) -> None:
        self.specs = tuple(specs)
        self.governance = dict(governance or {})
        self._by_id = {spec.source_id: spec for spec in self.specs}
        self.validate()

    @classmethod
    def from_json(cls, path: str | Path = "config/source_registry.json") -> "SourceRegistry":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            (SourceSpec.from_dict(row) for row in payload.get("sources", [])),
            governance=payload.get("governance") or {},
        )

    def validate(self) -> None:
        if len(self._by_id) != len(self.specs):
            raise ValueError("source registry contains duplicate source_id values")
        if not self.specs:
            raise ValueError("source registry must not be empty")
        for spec in self.specs:
            if not spec.source_id.strip():
                raise ValueError("source_id must not be empty")
            if spec.owner_ai not in _ALLOWED_AI_ROLES:
                raise ValueError(f"unknown owner_ai for {spec.source_id}: {spec.owner_ai}")
            if spec.cadence_seconds < 1:
                raise ValueError(f"invalid cadence for {spec.source_id}")
            if spec.content_trust in _HOSTILE_TRUST and not spec.browser_isolation:
                raise ValueError(f"hostile source must require browser isolation: {spec.source_id}")
            if spec.activation == "active" and not spec.implemented:
                raise ValueError(f"active source has no implementation: {spec.source_id}")
            if spec.credential_env and spec.credential_options:
                raise ValueError(f"use credential_env or credential_options, not both: {spec.source_id}")
            if any(not option for option in spec.credential_options):
                raise ValueError(f"empty credential option for {spec.source_id}")
        if self.governance.get("external_content_is_untrusted") is not True:
            raise ValueError("registry governance must treat external content as untrusted")
        if self.governance.get("allow_commands_from_content") is not False:
            raise ValueError("registry governance must forbid commands from source content")
        if self.governance.get("historical_evidence_is_immutable") is not True:
            raise ValueError("registry governance must preserve historical evidence")

    def get(self, source_id: str) -> SourceSpec | None:
        return self._by_id.get(source_id)

    def by_domain(self, domain: str) -> list[SourceSpec]:
        return [spec for spec in self.specs if spec.domain == domain]

    def due_sources(
        self,
        last_success_at: dict[str, str | None],
        *,
        now: datetime | None = None,
    ) -> list[SourceSpec]:
        now = now or datetime.now(timezone.utc)
        due: list[SourceSpec] = []
        for spec in self.specs:
            if not spec.can_run or spec.runtime_mode in _DELEGATED_RUNTIME_MODES:
                continue
            value = last_success_at.get(spec.source_id)
            if not value:
                due.append(spec)
                continue
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                due.append(spec)
                continue
            if (now - parsed.astimezone(timezone.utc)).total_seconds() >= spec.cadence_seconds:
                due.append(spec)
        return sorted(due, key=lambda row: (row.cadence_seconds, row.source_id))

    def summary(self) -> dict[str, object]:
        active = [spec for spec in self.specs if spec.activation.startswith("active")]
        planned = [spec for spec in self.specs if spec.activation.startswith("planned")]
        blocked = [spec for spec in self.specs if spec.activation.startswith("blocked")]
        return {
            "schema_version": "geowatch-source-registry-summary-v2",
            "source_count": len(self.specs),
            "active_count": len(active),
            "planned_count": len(planned),
            "blocked_count": len(blocked),
            "missing_credentials": {
                spec.source_id: list(spec.missing_credentials())
                for spec in self.specs
                if spec.missing_credentials()
            },
            "domains": sorted({spec.domain for spec in self.specs}),
            "delegated_runtime_modes": sorted(_DELEGATED_RUNTIME_MODES),
        }


def load_registry(path: str | Path = "config/source_registry.json") -> SourceRegistry:
    return SourceRegistry.from_json(path)
