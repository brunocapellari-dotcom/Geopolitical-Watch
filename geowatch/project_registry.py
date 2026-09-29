from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectService:
    service_id: str
    required: bool


@dataclass(frozen=True)
class ProjectRegistry:
    project_id: str
    display_name: str
    canonical_repository: str
    canonical_production_target: str
    runtime_bridge: str | None
    services: tuple[ProjectService, ...]
    required_gates: tuple[str, ...]

    @classmethod
    def from_json(cls, path: str | Path = "config/project_registry.json") -> "ProjectRegistry":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        services = tuple(
            ProjectService(service_id=str(row["service_id"]), required=bool(row.get("required", True)))
            for row in payload.get("services", [])
        )
        registry = cls(
            project_id=str(payload["project_id"]),
            display_name=str(payload["display_name"]),
            canonical_repository=str(payload["canonical_repository"]),
            canonical_production_target=str(payload["canonical_production_target"]),
            runtime_bridge=str(payload["runtime_bridge"]) if payload.get("runtime_bridge") else None,
            services=services,
            required_gates=tuple(str(value) for value in payload.get("required_gates", [])),
        )
        registry.validate()
        return registry

    def validate(self) -> None:
        if not self.project_id.strip() or not self.canonical_repository.strip():
            raise ValueError("project registry identity fields are required")
        ids = [row.service_id for row in self.services]
        if len(ids) != len(set(ids)):
            raise ValueError("project registry contains duplicate service_id values")
        if not self.required_gates:
            raise ValueError("project registry must define release gates")

    def runtime_snapshot(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "repository": self.canonical_repository,
            "environment": os.environ.get("GEOWATCH_ENVIRONMENT", "development"),
            "git_commit": os.environ.get("GEOWATCH_GIT_COMMIT") or os.environ.get("COMMIT_SHA"),
            "release": os.environ.get("GEOWATCH_RELEASE", "unknown"),
            "services": [
                {"service_id": row.service_id, "required": row.required}
                for row in self.services
            ],
            "required_gates": list(self.required_gates),
        }


def load_project_registry(path: str | Path = "config/project_registry.json") -> ProjectRegistry:
    return ProjectRegistry.from_json(path)
