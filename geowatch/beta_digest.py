from __future__ import annotations

from datetime import datetime, timezone


def build_beta_digest(episode_report: dict, coverage: dict, *, max_episodes: int = 12) -> dict:
    sources = list(coverage.get("sources") or [])
    unhealthy = [row for row in sources if row.get("last_run_status") not in (None, "ok")]
    episode_rows = []
    for episode in list(episode_report.get("episodes") or [])[:max_episodes]:
        recent = list(episode.get("recent_events") or [])
        recent_sources: list[str] = []
        for event in recent:
            label = str(event.get("publisher") or event.get("source_id") or "unknown")
            if label not in recent_sources:
                recent_sources.append(label)
        strength = episode.get("evidence_strength") or {}
        episode_rows.append({
            "episode_id": episode.get("episode_id"),
            "title": episode.get("title"),
            "state": episode.get("state"),
            "countries": list(episode.get("countries") or []),
            "last_updated_at": episode.get("last_updated_at"),
            "evidence_strength_index": strength.get("overall_index"),
            "evidence_strength_not_probability": True,
            "change_flags": list(episode.get("change_flags") or []),
            "claim_count": len(episode.get("claims") or []),
            "evidence_count": len(episode.get("evidence") or []),
            "recent_event_count": len(recent),
            "recent_sources": recent_sources[:8],
        })
    return {
        "schema_version": "geowatch-public-beta-digest-v1",
        "generated_at": episode_report.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "source_health": {
            "source_count": len(sources),
            "unhealthy_source_count": len(unhealthy),
            "all_last_runs_ok": not unhealthy,
            "sources": sources,
        },
        "episode_count_in_report": int(episode_report.get("episode_count") or len(episode_report.get("episodes") or [])),
        "episodes_in_digest": len(episode_rows),
        "top_episodes": episode_rows,
        "methodology": {
            "digest_is_triage_not_intelligence_confirmation": True,
            "evidence_strength_is_not_probability": True,
            "strategic_context_is_not_event_evidence": True,
            "absence_from_digest_does_not_mean_absence_of_conflict": True,
        },
    }


def render_beta_digest_markdown(digest: dict) -> str:
    health = digest.get("source_health") or {}
    lines = [
        "# Geopolitical Watch — Public Beta Digest",
        "",
        f"Generated: {digest.get('generated_at')}",
        f"Sources: {health.get('source_count', 0)} | unhealthy: {health.get('unhealthy_source_count', 0)}",
        f"Episodes in report: {digest.get('episode_count_in_report', 0)} | shown: {digest.get('episodes_in_digest', 0)}",
        "",
        "> Triage view only. Evidence-strength indices are not probabilities, and strategic context does not verify events.",
        "",
        "## Source health",
        "",
    ]
    for source in health.get("sources") or []:
        lines.append(
            f"- **{source.get('source_id')}** — status={source.get('last_run_status')} | "
            f"last_records={source.get('last_run_records')} | last_reference={source.get('last_reference_in_bounded_sample')}"
        )
    lines += ["", "## Priority episodes", ""]
    for index, episode in enumerate(digest.get("top_episodes") or [], 1):
        countries = ", ".join(episode.get("countries") or []) or "n/a"
        flags = ", ".join(episode.get("change_flags") or []) or "none"
        sources = ", ".join(episode.get("recent_sources") or []) or "n/a"
        lines += [
            f"### {index}. {episode.get('title')}",
            "",
            f"- State: **{episode.get('state')}**",
            f"- Countries: {countries}",
            f"- Last update: {episode.get('last_updated_at')}",
            f"- Evidence-strength index: {episode.get('evidence_strength_index')} *(not probability)*",
            f"- Change flags: {flags}",
            f"- Claims/evidence/recent events: {episode.get('claim_count')}/{episode.get('evidence_count')}/{episode.get('recent_event_count')}",
            f"- Recent sources: {sources}",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"
