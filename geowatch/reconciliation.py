from __future__ import annotations

from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Iterable

from .core import title_similarity
from .models import Event


def _date(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _distance_km(a: Event, b: Event) -> float | None:
    if None in (a.latitude, a.longitude, b.latitude, b.longitude):
        return None
    lat1, lon1, lat2, lon2 = map(radians, [a.latitude, a.longitude, b.latitude, b.longitude])  # type: ignore[arg-type]
    dlat, dlon = lat2-lat1, lon2-lon1
    h = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 6371.0088 * 2 * asin(sqrt(h))


def _actor_overlap(a: Event, b: Event) -> float:
    left={x.casefold().strip() for x in a.actors if x}; right={x.casefold().strip() for x in b.actors if x}
    if not left or not right: return 0.0
    return len(left & right) / len(left | right)


def match_score(a: Event, b: Event, *, max_days: int = 3, max_km: float = 100.0) -> dict:
    if a.country and b.country and a.country.casefold() != b.country.casefold():
        return {"score":0.0,"country_match":False,"date_days":None,"distance_km":None}
    days=abs((_date(a.reference_at)-_date(b.reference_at)).total_seconds())/86400
    if days > max_days:
        return {"score":0.0,"country_match":True,"date_days":round(days,3),"distance_km":None}
    distance=_distance_km(a,b)
    geo = 0.5 if distance is None else max(0.0, 1.0-distance/max_km) if distance <= max_km else 0.0
    temporal=max(0.0,1.0-days/max_days)
    actors=_actor_overlap(a,b)
    text=title_similarity(a.title,b.title)
    score=0.34*geo+0.28*temporal+0.28*actors+0.10*text
    return {"score":round(score,4),"country_match":True,"date_days":round(days,3),"distance_km":round(distance,2) if distance is not None else None,"actor_overlap":round(actors,4),"title_similarity":round(text,4)}


def reconcile(primary: Iterable[Event], secondary: Iterable[Event], *, threshold: float = 0.45) -> dict:
    left=list(primary); right=list(secondary); matches=[]; used:set[str]=set()
    for event in left:
        candidates=[]
        for other in right:
            if other.event_id in used: continue
            details=match_score(event,other)
            if details["score"] >= threshold:
                candidates.append((float(details["score"]),other,details))
        if not candidates: continue
        _,other,details=max(candidates,key=lambda row:row[0]); used.add(other.event_id)
        matches.append({"primary_event_id":event.event_id,"secondary_event_id":other.event_id,"match":details})
    matched_left={row["primary_event_id"] for row in matches}
    return {
        "schema_version":"geowatch-cross-source-reconciliation-v1",
        "matches":matches,
        "primary_unmatched":[e.event_id for e in left if e.event_id not in matched_left],
        "secondary_unmatched":[e.event_id for e in right if e.event_id not in used],
        "divergence_is_not_automatically_error":True,
        "methodology_notes":["Matching is analytical reconciliation, not identity proof.","Fatality or classification differences remain preserved per provider."],
    }
