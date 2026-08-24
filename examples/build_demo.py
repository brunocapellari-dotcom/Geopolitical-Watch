from geowatch.core import cluster_events
from geowatch.models import Event
from geowatch.reports import build_report, render_markdown
from geowatch.storage import SQLiteStore

stamp = "2026-08-24T15:00:00+00:00"
events = [
    Event(event_id="demo-reuters", source_id="gdelt", source_kind="news", title="Missile attack disrupts major port operations", event_type="media_report", reference_at=stamp, published_at=stamp, collected_at=stamp, verification_level="osint_signal", source_url="https://reuters.example/demo", publisher="reuters.example", impact_areas=("shipping","logistics")),
    Event(event_id="demo-bbc", source_id="gdelt", source_kind="news", title="Missile attack disrupts major port operations", event_type="media_report", reference_at=stamp, published_at=stamp, collected_at=stamp, verification_level="osint_signal", source_url="https://bbc.example/demo", publisher="bbc.example", impact_areas=("shipping","logistics")),
]
clusters = cluster_events(events)
report = build_report(clusters, generated_at=stamp)
markdown = render_markdown(report)
store = SQLiteStore("data/geowatch.db")
store.upsert_events(events)
store.upsert_clusters(clusters, stamp)
store.upsert_report(report, markdown)
store.close()
print(report["report_id"])
