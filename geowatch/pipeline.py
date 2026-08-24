from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .core import cluster_events
from .reports import build_report, render_markdown
from .sources import firms, gdelt, reliefweb, ucdp
from .storage import SQLiteStore


def run(config_path: str | Path = "config/sources.json", db_path: str | Path = "data/geowatch.db", raw_root: str | Path = "data/raw", reports_root: str | Path = "reports") -> dict:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    collected_at = datetime.now(timezone.utc).isoformat()
    raw_root = Path(raw_root)
    all_events = []
    source_results = []

    for spec in config.get("sources", []):
        if not spec.get("enabled", False):
            continue
        source_id = spec["source_id"]
        kind = spec["kind"]
        try:
            payloads: list[bytes]
            urls: list[str]
            if kind == "gdelt":
                payload, url = gdelt.collect(query=spec.get("query", gdelt.DEFAULT_QUERY), timespan=spec.get("timespan", "24H"), maxrecords=int(spec.get("maxrecords", 250)))
                payloads, urls = [payload], [url]
                parser = gdelt.parse
            elif kind == "reliefweb":
                payload, url = reliefweb.collect(query=spec.get("query", "conflict war hostilities displacement"), limit=int(spec.get("limit", 100)))
                payloads, urls = [payload], [url]
                parser = reliefweb.parse
            elif kind == "ucdp":
                payloads, urls = ucdp.collect_all(version=spec.get("version", ucdp.DEFAULT_VERSION), pagesize=int(spec.get("pagesize", 1000)))
                parser = ucdp.parse
            elif kind == "firms":
                payload, url = firms.collect(sensor=spec.get("sensor", "VIIRS_SNPP_NRT"), area=spec.get("area", "world"), day_range=int(spec.get("day_range", 1)))
                payloads, urls = [payload], [url]
                parser = firms.parse
            else:
                raise ValueError(f"Unknown source kind: {kind}")

            count = 0
            for payload in payloads:
                digest = hashlib.sha256(payload).hexdigest()
                day = collected_at[:10]
                path = raw_root / source_id / day / f"{digest}.{spec.get('extension','json')}"
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_bytes(payload)
                events = parser(payload, source_id=source_id, collected_at=collected_at, raw_ref=str(path))
                all_events.extend(events)
                count += len(events)
            source_results.append({"source_id": source_id, "status": "ok", "records": count, "urls": urls})
        except Exception as exc:
            source_results.append({"source_id": source_id, "status": "error", "error": f"{type(exc).__name__}: {exc}"})

    clusters = cluster_events(all_events)
    report = build_report(
        clusters,
        generated_at=collected_at,
        min_priority=int(config.get("report", {}).get("min_priority", 0)),
        max_events=int(config.get("report", {}).get("max_events", 20)),
        max_news_per_event=int(config.get("report", {}).get("max_news_per_event", 5)),
    )
    markdown = render_markdown(report)

    store = SQLiteStore(db_path)
    store.upsert_events(all_events)
    store.upsert_clusters(clusters, collected_at)
    store.upsert_report(report, markdown)
    store.close()

    reports_root = Path(reports_root)
    day_dir = reports_root / collected_at[:10]
    day_dir.mkdir(parents=True, exist_ok=True)
    stamp = collected_at.replace(":", "-").replace("+", "_")
    (day_dir / f"{stamp}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (day_dir / f"{stamp}.md").write_text(markdown, encoding="utf-8")
    reports_root.mkdir(parents=True, exist_ok=True)
    (reports_root / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (reports_root / "latest.md").write_text(markdown, encoding="utf-8")

    return {"generated_at": collected_at, "source_results": source_results, "events": len(all_events), "clusters": len(clusters), "report_id": report["report_id"]}
