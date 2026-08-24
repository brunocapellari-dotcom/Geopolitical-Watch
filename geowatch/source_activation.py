from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping


class SourceActivationRegistry:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.sources = {row["source_id"]: row for row in payload.get("sources", [])}

    @classmethod
    def from_json(cls, path: str | Path = "config/operations/source_activation.json") -> "SourceActivationRegistry":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def evaluate(self, *, env: Mapping[str, str] | None = None, reviewed_terms: set[str] | None = None) -> dict:
        env = env or os.environ
        reviewed_terms = reviewed_terms or set()
        rows = []
        for source_id, source in self.sources.items():
            credentials = list(source.get("credential_env") or [])
            missing = [name for name in credentials if not env.get(name)]
            terms_required = bool(source.get("terms_gate"))
            terms_ok = (not terms_required) or source_id in reviewed_terms
            ready = not missing and terms_ok
            rows.append({
                "source_id": source_id,
                "configured_enabled": bool(source.get("enabled_now")),
                "activation_ready": ready,
                "missing_credentials": missing,
                "terms_required": terms_required,
                "terms_reviewed": terms_ok,
                "priority": source.get("priority"),
                "historical_backfill": bool(source.get("historical_backfill")),
            })
        return {
            "schema_version": "geowatch-source-activation-status-v1",
            "ready_sources": sorted(row["source_id"] for row in rows if row["activation_ready"]),
            "blocked_sources": sorted(row["source_id"] for row in rows if not row["activation_ready"]),
            "sources": rows,
            "single_source_block_does_not_block_pipeline": True,
        }

    def source(self, source_id: str) -> dict | None:
        row = self.sources.get(source_id)
        return dict(row) if row else None
