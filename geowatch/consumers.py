from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def load_profile(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_consumer_feed(store, profile: dict, *, generated_at: str | None = None) -> dict:
    generated = generated_at or datetime.now(timezone.utc).isoformat()
    allowed_states = set(profile.get("states") or ())
    allowed_countries = set(profile.get("countries") or ())
    allowed_impacts = set(profile.get("impact_areas") or ())
    min_strength = int(profile.get("min_strength", 0))
    max_episodes = int(profile.get("max_episodes", 100))
    episode_rows = store.load_episodes(limit=max_episodes * 3)
    output = []
    for episode in episode_rows:
        strength = episode.evidence_strength.overall_index if episode.evidence_strength else 0
        if strength < min_strength:
            continue
        if allowed_states and episode.state not in allowed_states:
            continue
        if allowed_countries and not (allowed_countries & set(episode.countries)):
            continue
        events = store.load_events_by_ids(episode.event_ids)
        impacts = sorted({area for event in events for area in event.impact_areas})
        if allowed_impacts and not (allowed_impacts & set(impacts)):
            continue
        selected_impacts = sorted(set(impacts) & allowed_impacts) if allowed_impacts else impacts
        output.append({
            "episode": episode.to_dict(),
            "matching_impact_areas": selected_impacts,
            "recent_events": [
                {
                    "event_id": event.event_id,
                    "title": event.title,
                    "reference_at": event.reference_at,
                    "verification_level": event.verification_level,
                    "publisher": event.publisher,
                    "source_url": event.source_url,
                    "impact_areas": list(event.impact_areas),
                }
                for event in sorted(events, key=lambda row: row.reference_at, reverse=True)[:10]
            ],
        })
        if len(output) >= max_episodes:
            break
    return {
        "schema_version": "geowatch-consumer-feed-v1",
        "provider": "Geopolitical Watch",
        "consumer_id": str(profile.get("consumer_id") or "unnamed"),
        "generated_at": generated,
        "read_only": True,
        "episodes": output,
    }


def consumer_profile_path(name: str, root: str | Path = "config/consumers") -> Path:
    safe = "".join(ch for ch in name.casefold() if ch.isalnum() or ch in {"-", "_"})
    if not safe or safe != name.casefold():
        raise ValueError("invalid consumer name")
    return Path(root) / f"{safe}.json"
