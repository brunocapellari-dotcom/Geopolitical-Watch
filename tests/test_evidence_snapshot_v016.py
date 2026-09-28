from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from geowatch.evidence_snapshot import snapshot_response
from geowatch.http import HttpResponse
from geowatch.raw_store import LocalRawStore


class EvidenceSnapshotTests(unittest.TestCase):
    def test_snapshot_persists_raw_payload_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalRawStore(Path(tmp) / "raw")
            response = HttpResponse(
                payload=b"<html><body>evidence</body></html>",
                url="https://example.org/final",
                content_type="text/html; charset=utf-8",
            )
            snapshot = snapshot_response(
                "source_a",
                "https://example.org/start",
                response,
                collected_at="2026-09-28T20:00:00+00:00",
                collector_id="collector-v1",
                raw_store=store,
            )

            self.assertEqual("https://example.org/start", snapshot.original_url)
            self.assertEqual("https://example.org/final", snapshot.final_url)
            self.assertEqual(34, len(snapshot.sha256))
            self.assertTrue(Path(snapshot.raw_ref).exists())
            self.assertEqual(b"<html><body>evidence</body></html>", Path(snapshot.raw_ref).read_bytes())

    def test_snapshot_keeps_original_and_final_url_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalRawStore(Path(tmp) / "raw")
            response = HttpResponse(
                payload=b'{"ok":true}',
                url="https://example.org/canonical",
                content_type="application/json",
            )
            snapshot = snapshot_response(
                "source_b",
                "https://example.org/redirecting",
                response,
                collected_at="2026-09-28T20:01:00+00:00",
                raw_store=store,
            )
            self.assertNotEqual(snapshot.original_url, snapshot.final_url)
            self.assertTrue(snapshot.raw_ref.endswith(".json"))


if __name__ == "__main__":
    unittest.main()
