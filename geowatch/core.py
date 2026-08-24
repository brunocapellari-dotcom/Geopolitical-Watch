from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from .models import Event, ImpactArea

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

_IMPACT_KEYWORDS: dict[ImpactArea, tuple[str, ...]] = {
    "energy": ("oil", "crude", "refinery", "pipeline", "tanker", "lng", "gas terminal"),
    "fertilizers": ("fertilizer", "fertiliser", "urea", "ammonia", "potash", "phosphate"),
    "shipping": ("port", "vessel", "ship", "tanker", "strait", "canal", "red sea", "black sea", "suez", "hormuz", "bab el-mandeb"),
    "trade": ("sanction", "embargo", "blockade", "export ban", "import ban", "tariff"),
    "fx": ("capital control", "currency intervention", "foreign exchange restriction"),
    "agriculture": ("grain", "wheat", "corn", "maize", "soybean", "sunflower", "crop", "grain terminal"),
    "logistics": ("bridge", "railway", "railroad", "rail line", "highway", "port", "canal", "border crossing"),
    "humanitarian": ("displacement", "refugee", "humanitarian", "evacuation", "food insecurity"),
    "infrastructure": ("power plant", "substation", "dam", "airport", "terminal", "bridge", "pipeline", "port"),
}

_ESCALATION_TERMS = (
    "airstrike", "air strike", "missile", "drone strike", "invasion", "offensive",
    "mobilization", "mobilisation", "blockade", "attack", "shelling", "ceasefire collapse",
)

_VERIFICATION_RANK = {
    "research_coded": 4,
    "curated_report": 3,
    "sensor_signal": 2,
    "osint_signal": 1,
}


@dataclass(frozen=True)
class EventCluster:
    canonical: Event
    members: tuple[Event, ...]

    @property
    def provider_count(self) -> int:
        return len({_provider_key(event) for event in self.members})

    @property
    def source_count(self) -> int:
        return len({event.source_id for event in self.members})

    def to_dict(self) -> dict[str, object]:
        return {
            "cluster_id": deterministic_cluster_id(self),
            "canonical": self.canonical.to_dict(),
            "member_event_ids": [event.event_id for event in self.members],
            "provider_count": self.provider_count,
            "source_count": self.source_count,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_event_id(source_id: str, source_event_id: str | None, title: str, reference_at: str, country: str | None) -> str:
    key = "|".join([
        source_id.strip().casefold(),
        (source_event_id or "").strip().casefold(),
        normalize_text(title),
        reference_at[:10],
        (country or "").strip().casefold(),
    ])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def deterministic_cluster_id(cluster: EventCluster) -> str:
    key = "|".join(sorted(event.event_id for event in cluster.members))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def infer_impact_areas(text: str) -> tuple[ImpactArea, ...]:
    normalized = normalize_text(text)
    found: list[ImpactArea] = []
    for area, phrases in _IMPACT_KEYWORDS.items():
        if any(contains_phrase(normalized, phrase) for phrase in phrases):
            found.append(area)
    return tuple(found)


def title_similarity(left: str, right: str) -> float:
    lt = set(_TOKEN_RE.findall(normalize_text(left)))
    rt = set(_TOKEN_RE.findall(normalize_text(right)))
    if not lt or not rt:
        return 0.0
    return len(lt & rt) / len(lt | rt)


def cluster_events(events: list[Event], threshold: float = 0.78) -> list[EventCluster]:
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")
    clusters: list[list[Event]] = []
    for event in events:
        matched = None
        for group in clusters:
            canonical = choose_canonical(group)
            if same_event_window(canonical, event) and title_similarity(canonical.title, event.title) >= threshold:
                matched = group
                break
        if matched is None:
            clusters.append([event])
        else:
            matched.append(event)
    return [EventCluster(choose_canonical(group), tuple(group)) for group in clusters]


def score_cluster(cluster: EventCluster) -> int:
    event = cluster.canonical
    base = {"research_coded": 45, "curated_report": 32, "sensor_signal": 20, "osint_signal": 15}[event.verification_level]
    fatalities = max(0, event.fatalities_best or 0)
    if fatalities >= 200:
        fatality_bonus = 25
    elif fatalities >= 50:
        fatality_bonus = 18
    elif fatalities >= 10:
        fatality_bonus = 10
    elif fatalities >= 1:
        fatality_bonus = 5
    else:
        fatality_bonus = 0
    corroboration_bonus = min(20, max(0, cluster.provider_count - 1) * 5)
    escalation_bonus = 10 if any(contains_phrase(normalize_text(event.title), term) for term in _ESCALATION_TERMS) else 0
    impact_bonus = min(10, len(event.impact_areas) * 2)
    return min(100, base + fatality_bonus + corroboration_bonus + escalation_bonus + impact_bonus)


def choose_canonical(events: list[Event]) -> Event:
    return max(events, key=lambda e: (_VERIFICATION_RANK[e.verification_level], e.fatalities_best or 0, len(e.title)))


def same_event_window(left: Event, right: Event) -> bool:
    if left.reference_at[:10] != right.reference_at[:10]:
        return False
    if left.country and right.country and left.country.casefold() != right.country.casefold():
        return False
    return True


def corroboration_status(cluster: EventCluster) -> str:
    levels = {event.verification_level for event in cluster.members}
    if "research_coded" in levels:
        return "research_coded"
    if "curated_report" in levels and cluster.provider_count >= 2:
        return "curated_and_corroborated"
    if "curated_report" in levels:
        return "curated_report"
    if "sensor_signal" in levels and cluster.provider_count >= 2:
        return "sensor_and_corroborated"
    if cluster.provider_count >= 2:
        return "multi_provider_osint"
    return "single_provider_signal"


def normalize_text(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def contains_phrase(normalized_text: str, phrase: str) -> bool:
    text_tokens = _TOKEN_RE.findall(normalized_text)
    phrase_tokens = _TOKEN_RE.findall(normalize_text(phrase))
    if not phrase_tokens or len(phrase_tokens) > len(text_tokens):
        return False
    width = len(phrase_tokens)
    return any(text_tokens[i:i+width] == phrase_tokens for i in range(len(text_tokens) - width + 1))


def publisher_from_url(url: str | None) -> str | None:
    if not url:
        return None
    host = (urlparse(url).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host or None


def _provider_key(event: Event) -> str:
    if event.publisher:
        return f"publisher:{event.publisher.casefold()}"
    if event.source_url:
        host = publisher_from_url(event.source_url)
        if host:
            return f"publisher:{host}"
    return f"source:{event.source_id.casefold()}"
