from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class MaritimeNotice:
    notice_id: str
    authority: str
    notice_type: str
    title: str
    issued_at: str
    valid_from: str | None = None
    valid_to: str | None = None
    status: str = "in_force"
    navarea: str | None = None
    area_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    hazard_types: tuple[str, ...] = ()
    source_url: str | None = None
    source_record_id: str | None = None

    def to_dict(self) -> dict:
        row = asdict(self)
        row["hazard_types"] = list(self.hazard_types)
        return row


def normalize_notice(*, authority: str, notice_type: str, title: str, issued_at: str,
                     valid_from: str | None = None, valid_to: str | None = None,
                     status: str = "in_force", navarea: str | None = None, area_name: str | None = None,
                     latitude: float | None = None, longitude: float | None = None,
                     hazard_types: Iterable[str] = (), source_url: str | None = None,
                     source_record_id: str | None = None) -> MaritimeNotice:
    fingerprint = "|".join([authority, notice_type, source_record_id or "", title, issued_at])
    notice_id = "mwn_" + hashlib.sha256(fingerprint.encode()).hexdigest()[:20]
    return MaritimeNotice(
        notice_id=notice_id, authority=authority, notice_type=notice_type, title=title,
        issued_at=issued_at, valid_from=valid_from, valid_to=valid_to, status=status,
        navarea=navarea, area_name=area_name, latitude=latitude, longitude=longitude,
        hazard_types=tuple(sorted(set(hazard_types))), source_url=source_url,
        source_record_id=source_record_id,
    )


def active_notices(rows: Iterable[MaritimeNotice], *, as_of: str | None = None) -> list[MaritimeNotice]:
    result = []
    for row in rows:
        if row.status in {"cancelled", "expired"}:
            continue
        if as_of is not None and row.valid_from and row.valid_from > as_of:
            continue
        if as_of is not None and row.valid_to and row.valid_to < as_of:
            continue
        result.append(row)
    return result


def maritime_context(rows: Iterable[MaritimeNotice], *, navareas: Iterable[str] = (), area_terms: Iterable[str] = ()) -> dict:
    navareas = set(navareas)
    terms = [term.casefold() for term in area_terms]
    matched = []
    for row in rows:
        navarea_match = not navareas or (row.navarea and row.navarea in navareas)
        area_text = f"{row.area_name or ''} {row.title}".casefold()
        term_match = not terms or any(term in area_text for term in terms)
        if navarea_match and term_match:
            matched.append(row)
    return {
        "schema_version": "geowatch-maritime-context-v1",
        "context_not_conflict_attribution": True,
        "notice_count": len(matched),
        "hazard_types": sorted({hazard for row in matched for hazard in row.hazard_types}),
        "notices": [row.to_dict() for row in matched],
        "methodology_notes": [
            "Navigational warnings are authoritative for navigation-safety context within their scope, but do not by themselves establish conflict attribution or intent.",
            "Cancellation, validity window and issuing authority must be preserved.",
            "Web-published warnings are contextual data and do not replace approved maritime broadcast systems for navigation decisions.",
        ],
    }
