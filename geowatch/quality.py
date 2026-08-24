from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from .models import Event


@dataclass(frozen=True)
class SourceProfile:
    source_id: str
    governance_class: str
    evidence_role: str
    official_or_primary: bool
    update_cadence: str | None = None
    credential_env: str | None = None
    backfill_capability: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def load_profiles(path: str | Path | None) -> dict[str, SourceProfile]:
    if path is None:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    body = json.loads(file_path.read_text(encoding="utf-8"))
    profiles: dict[str, SourceProfile] = {}
    for row in body.get("sources", []):
        profile = SourceProfile(
            source_id=row["source_id"],
            governance_class=row["governance_class"],
            evidence_role=row["evidence_role"],
            official_or_primary=bool(row.get("official_or_primary", False)),
            update_cadence=row.get("update_cadence"),
            credential_env=row.get("credential_env"),
            backfill_capability=row.get("backfill_capability"),
            notes=row.get("notes"),
        )
        profiles[profile.source_id] = profile
    return profiles


def event_quality_metadata(event: Event, profiles: Mapping[str, SourceProfile] | None = None) -> dict[str, object]:
    profile = profiles.get(event.source_id) if profiles else None
    return {
        "source_profile": profile.to_dict() if profile else None,
        "publisher_resolved": bool(event.publisher),
        "has_source_url": bool(event.source_url),
        "has_coordinates": event.latitude is not None and event.longitude is not None,
        "has_country": bool(event.country),
        "verification_level": event.verification_level,
    }
