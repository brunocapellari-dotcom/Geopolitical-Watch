from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from geowatch.api import Handler
from geowatch.models import Entity, Relationship
from geowatch.storage import SQLiteStore


class RelationshipApiTests(unittest.TestCase):
    def test_relationship_endpoint_is_read_only_and_filterable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "api.db"
            store = SQLiteStore(db)
            try:
                store.upsert_entities([
                    Entity(entity_id="entity_a", entity_type="actor", canonical_name="Actor A"),
                    Entity(entity_id="entity_b", entity_type="port", canonical_name="Port B"),
                ])
                store.upsert_relationships([
                    Relationship(
                        relationship_id="rel_api",
                        source_entity_id="entity_a",
                        target_entity_id="entity_b",
                        relationship_type="controls",
                        semantic_class="derived",
                        first_seen_at="2026-09-28T20:00:00Z",
                        last_seen_at="2026-09-28T20:05:00Z",
                        valid_from="2026-09-20T00:00:00Z",
                        evidence_ids=("ev_1",),
                        source_ids=("src_1",),
                    )
                ])
            finally:
                store.close()

            previous = os.environ.get("GEOWATCH_DB")
            os.environ["GEOWATCH_DB"] = str(db)
            try:
                with running_server() as base:
                    with urlopen(base + "/v2/relationships?entity_id=entity_a") as response:
                        payload = json.load(response)
                self.assertEqual("geowatch-relationships-v1", payload["schema_version"])
                self.assertEqual(1, len(payload["relationships"]))
                self.assertEqual("rel_api", payload["relationships"][0]["relationship_id"])
                self.assertEqual("2026-09-20T00:00:00Z", payload["relationships"][0]["valid_from"])
            finally:
                if previous is None:
                    os.environ.pop("GEOWATCH_DB", None)
                else:
                    os.environ["GEOWATCH_DB"] = previous


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
