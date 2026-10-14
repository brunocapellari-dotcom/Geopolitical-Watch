from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from geowatch.api import Handler
from geowatch.storage import SQLiteStore


class PointInTimeHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "history.db"
        self.store = SQLiteStore(self.db_path)

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_snapshot_uses_only_state_known_at_cutoff(self) -> None:
        self.store.record_versions(
            "claim_verdict",
            [("claim-1", {"verdict": "RELATADO", "confidence": 35})],
            recorded_at="2026-10-07T10:00:00+00:00",
        )
        self.store.record_versions(
            "claim_verdict",
            [("claim-1", {"verdict": "CONFIRMADO", "confidence": 90})],
            recorded_at="2026-10-07T12:00:00+00:00",
        )

        before = self.store.snapshot_as_of(
            "2026-10-07T11:00:00+00:00",
            object_type="claim_verdict",
        )
        after = self.store.snapshot_as_of(
            "2026-10-07T13:00:00+00:00",
            object_type="claim_verdict",
        )

        self.assertEqual(before[0]["payload"]["verdict"], "RELATADO")
        self.assertEqual(before[0]["payload"]["confidence"], 35)
        self.assertEqual(after[0]["payload"]["verdict"], "CONFIRMADO")
        self.assertEqual(after[0]["payload"]["confidence"], 90)

    def test_reversion_to_earlier_payload_is_preserved_as_new_version(self) -> None:
        state_a = {"status": "RELATADO", "confidence": 40}
        state_b = {"status": "CONTESTADO", "confidence": 25}

        self.assertEqual(
            1,
            self.store.record_versions(
                "claim",
                [("claim-2", state_a)],
                recorded_at="2026-10-07T10:00:00+00:00",
            ),
        )
        self.assertEqual(
            1,
            self.store.record_versions(
                "claim",
                [("claim-2", state_b)],
                recorded_at="2026-10-07T12:00:00+00:00",
            ),
        )
        self.assertEqual(
            1,
            self.store.record_versions(
                "claim",
                [("claim-2", state_a)],
                recorded_at="2026-10-07T14:00:00+00:00",
            ),
        )
        self.assertEqual(3, len(self.store.list_versions("claim", "claim-2")))

        self.assertEqual(
            0,
            self.store.record_versions(
                "claim",
                [("claim-2", state_a)],
                recorded_at="2026-10-07T16:00:00+00:00",
            ),
        )
        self.assertEqual(3, len(self.store.list_versions("claim", "claim-2")))

    def test_history_api_exposes_versions_and_as_of_snapshot(self) -> None:
        self.store.record_versions(
            "claim_verdict",
            [("claim-api", {"verdict": "RELATADO", "confidence": 30})],
            recorded_at="2026-10-07T10:00:00+00:00",
        )
        self.store.record_versions(
            "claim_verdict",
            [("claim-api", {"verdict": "CORROBORADO", "confidence": 70})],
            recorded_at="2026-10-07T12:00:00+00:00",
        )
        self.store.close()

        old = os.environ.get("GEOWATCH_DB")
        os.environ["GEOWATCH_DB"] = str(self.db_path)
        try:
            with running_server() as base:
                snapshot_query = urlencode({
                    "as_of": "2026-10-07T11:00:00+00:00",
                    "object_type": "claim_verdict",
                })
                with urlopen(base + "/v2/history/snapshot?" + snapshot_query) as response:
                    snapshot = json.load(response)
                versions_query = urlencode({
                    "object_type": "claim_verdict",
                    "object_id": "claim-api",
                })
                with urlopen(base + "/v2/history/versions?" + versions_query) as response:
                    versions = json.load(response)
            self.assertEqual("geowatch-point-in-time-snapshot-v1", snapshot["schema_version"])
            self.assertEqual("RELATADO", snapshot["objects"][0]["payload"]["verdict"])
            self.assertEqual(2, len(versions["versions"]))
            self.assertEqual("CORROBORADO", versions["versions"][-1]["payload"]["verdict"])
        finally:
            if old is None:
                os.environ.pop("GEOWATCH_DB", None)
            else:
                os.environ["GEOWATCH_DB"] = old
            self.store = SQLiteStore(self.db_path)


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
