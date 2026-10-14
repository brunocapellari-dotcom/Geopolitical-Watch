from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from geowatch.api import Handler
from geowatch.convergence import converge_events
from geowatch.entities import EntityResolver
from geowatch.models import Event
from geowatch.storage import SQLiteStore


class MinimumOperationalApiTests(unittest.TestCase):
    def test_sources_regions_timeline_actors_and_alerts_contracts(self) -> None:
        event = Event(
            event_id="api-min-1",
            source_id="test",
            source_kind="news",
            title="Port disruption reported",
            event_type="media_report",
            reference_at="2026-10-08T10:00:00+00:00",
            collected_at="2026-10-08T10:01:00+00:00",
            verification_level="osint_signal",
            country="Exampleland",
            region="Coastal Region",
            publisher="Example Publisher",
        )
        resolver = EntityResolver()
        episodes, claims, evidence, entities, changes = converge_events(
            [event],
            resolver=resolver,
            now=datetime(2026, 10, 8, 12, tzinfo=timezone.utc),
        )

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "api.db"
            store = SQLiteStore(db)
            store.upsert_events([event])
            store.upsert_entities(entities)
            store.upsert_evidence(evidence)
            store.upsert_claims(claims)
            store.upsert_episodes(episodes)
            store.record_changes(changes)
            store.close()

            old = os.environ.get("GEOWATCH_DB")
            os.environ["GEOWATCH_DB"] = str(db)
            try:
                with running_server() as base:
                    with urlopen(base + "/v2/source-health") as response:
                        health = json.load(response)
                    with urlopen(base + "/v2/sources") as response:
                        sources = json.load(response)
                    with urlopen(base + "/v2/regions") as response:
                        regions = json.load(response)
                    with urlopen(base + "/v2/timeline?since=2026-10-08T00:00:00%2B00:00") as response:
                        timeline = json.load(response)
                    with urlopen(base + "/v2/actors") as response:
                        actors = json.load(response)
                    with urlopen(base + "/v2/alerts") as response:
                        alerts = json.load(response)
            finally:
                if old is None:
                    os.environ.pop("GEOWATCH_DB", None)
                else:
                    os.environ["GEOWATCH_DB"] = old

        self.assertEqual("geowatch-source-health-v1", health["schema_version"])
        self.assertEqual("geowatch-sources-api-v1", sources["schema_version"])
        self.assertTrue(sources["sources"])
        self.assertEqual("geowatch-regions-v1", regions["schema_version"])
        self.assertTrue(any(row["country"] == "Exampleland" for row in regions["regions"]))
        self.assertEqual("geowatch-timeline-v1", timeline["schema_version"])
        self.assertTrue(timeline["changes"])
        self.assertEqual("geowatch-actor-profile-list-v1", actors["schema_version"])
        self.assertEqual("geowatch-alert-outbox-v1", alerts["schema_version"])


@contextmanager
def running_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


if __name__ == "__main__":
    unittest.main()
