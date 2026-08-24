from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Iterable, Mapping

from .core import EventCluster, corroboration_status, score_cluster
from .quality import SourceProfile, event_quality_metadata


def build_report(clusters: Iterable[EventCluster], *, report_type: str = "situational", generated_at: str | None = None, min_priority: int = 0, max_events: int = 20, max_news_per_event: int = 5, source_profiles: Mapping[str, SourceProfile] | None = None) -> dict:
    generated = generated_at or datetime.now(timezone.utc).isoformat()
    ranked = sorted(((score_cluster(c), c) for c in clusters), key=lambda x: (x[0], x[1].canonical.reference_at), reverse=True)
    selected = [(score, cluster) for score, cluster in ranked if score >= min_priority][:max_events]
    rows = []
    total_news = 0
    for score, cluster in selected:
        canonical = cluster.canonical
        news = []
        seen_urls: set[str] = set()
        for event in sorted(cluster.members, key=lambda e: e.published_at or e.reference_at, reverse=True):
            if event.source_kind != "news":
                continue
            if event.source_url and event.source_url in seen_urls:
                continue
            if event.source_url:
                seen_urls.add(event.source_url)
            news.append({
                "title": event.title,
                "publisher": event.publisher or event.source_id,
                "published_at": event.published_at,
                "url": event.source_url,
                "source_id": event.source_id,
                "quality_metadata": event_quality_metadata(event, source_profiles),
            })
            if len(news) >= max_news_per_event:
                break
        total_news += len(news)
        evidence = [
            {
                "title": event.title,
                "source_id": event.source_id,
                "publisher": event.publisher,
                "verification_level": event.verification_level,
                "url": event.source_url,
                "published_at": event.published_at,
                "quality_metadata": event_quality_metadata(event, source_profiles),
            }
            for event in cluster.members if event.source_kind != "news"
        ]
        rows.append({
            "cluster_id": cluster.to_dict()["cluster_id"],
            "event_id": canonical.event_id,
            "title": canonical.title,
            "priority_score": score,
            "priority_method_version": "geowatch-priority-v0.4",
            "corroboration_status": corroboration_status(cluster),
            "verification_level": canonical.verification_level,
            "reference_at": canonical.reference_at,
            "country": canonical.country,
            "region": canonical.region,
            "latitude": canonical.latitude,
            "longitude": canonical.longitude,
            "fatalities_best": canonical.fatalities_best,
            "actors": list(canonical.actors),
            "impact_areas": list(canonical.impact_areas),
            "impact_evidence_class": canonical.impact_evidence_class,
            "provider_count": cluster.provider_count,
            "canonical_quality_metadata": event_quality_metadata(canonical, source_profiles),
            "evidence": evidence,
            "news": news,
            "news_count": len(news),
            "what_to_watch": _what_to_watch(canonical.impact_areas),
        })
    report_id = hashlib.sha256((report_type + "|" + generated + "|" + "|".join(r["cluster_id"] for r in rows)).encode()).hexdigest()[:24]
    return {
        "schema_version": "geowatch-report-v1",
        "report_id": report_id,
        "report_type": report_type,
        "generated_at": generated,
        "event_count": len(rows),
        "news_count": total_news,
        "events": rows,
        "methodology_notes": [
            "News coverage is an observed publication signal, not automatic confirmation of the reported fact.",
            "Thermal and other sensor signals require independent corroboration before conflict attribution.",
            "Priority score ranks analyst attention; it is not a probability of war or economic impact.",
            "Impact areas are inferred tags until causal analysis validates or rejects them.",
        ],
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Geopolitical Watch — Situational Report",
        "",
        f"Generated: {report['generated_at']}",
        f"Selected events: {report['event_count']} | Related news: {report['news_count']}",
        "",
    ]
    for index, event in enumerate(report.get("events", []), 1):
        lines += [
            f"## {index}. {event['title']}", "",
            f"**Priority:** {event['priority_score']}/100  ",
            f"**Evidence status:** {event['corroboration_status']}  ",
            f"**Verification:** {event['verification_level']}  ",
            f"**Reference:** {event['reference_at']}  ",
        ]
        if event.get("country"):
            lines.append(f"**Location:** {event['country']}{' / ' + event['region'] if event.get('region') else ''}  ")
        if event.get("impact_areas"):
            lines.append(f"**Potential impact areas (inferred):** {', '.join(event['impact_areas'])}  ")
        lines.append("")
        if event.get("evidence"):
            lines += ["### Coded / curated / sensor evidence", ""]
            for item in event["evidence"]:
                suffix = f" — {item['url']}" if item.get("url") else ""
                lines.append(f"- {item['publisher'] or item['source_id']}: {item['title']} ({item['verification_level']}){suffix}")
            lines.append("")
        lines += ["### Related news", ""]
        if event.get("news"):
            for item in event["news"]:
                when = f" — {item['published_at']}" if item.get("published_at") else ""
                link = f" — {item['url']}" if item.get("url") else ""
                lines.append(f"- **{item['publisher']}**: {item['title']}{when}{link}")
        else:
            lines.append("- No preserved related news in this cluster.")
        lines += ["", "### What to watch", ""]
        for item in event.get("what_to_watch", []):
            lines.append(f"- {item}")
        lines.append("")
    lines += ["## Methodology", ""]
    for note in report.get("methodology_notes", []):
        lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def build_feed(report: dict) -> dict:
    return {
        "schema_version": "geowatch-feed-v1",
        "provider": "Geopolitical Watch",
        "generated_at": report["generated_at"],
        "report_id": report["report_id"],
        "events": report["events"],
    }


def _what_to_watch(areas: tuple[str, ...]) -> list[str]:
    mapping = {
        "energy": "Verify production, refining, pipeline, terminal, crude and fuel effects.",
        "fertilizers": "Track ammonia, urea, potash, phosphates, sanctions and supply routes.",
        "shipping": "Track route closures/diversions, insurance, voyage time, freight and congestion.",
        "trade": "Track sanctions, embargoes, export/import restrictions and trade rerouting.",
        "fx": "Track currency reaction and transmission into dollar-linked costs.",
        "agriculture": "Track grains/oilseeds availability, exports, premiums and origin substitution.",
        "logistics": "Track ports, rail, roads, canals, borders and alternate capacity.",
        "humanitarian": "Track displacement, aid access and secondary food-security effects.",
        "infrastructure": "Confirm physical damage, operational status, redundancy and restoration time.",
    }
    return [mapping[a] for a in areas if a in mapping] or ["Seek additional corroboration and test for material downstream effects."]
