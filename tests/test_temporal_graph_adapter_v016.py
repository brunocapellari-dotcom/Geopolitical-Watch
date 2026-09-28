from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from geowatch.models import Relationship
from geowatch.storage import SQLiteStore
from geowatch.temporal_graph_adapter import persist_derived_relationships, validate_derived_relationship


class TemporalGraphAdapterTests(unittest.TestCase):
    def test_rejects_observed_relationship_from_derived_graph(self) -> None:
        with self.assertRaises(ValueError):
            validate_derived_relationship(Relationship(
                relationship_id="rel_observed",
                source_entity_id="a",
                target_entity_id="b",
                relationship_type="located_at",
                semantic_class="observed",
                first_seen_at="2026-09-28T20:00:00Z",
                last_seen_at="2026-09-28T20:00:00Z",
                evidence_ids=("ev_1",),
            ))

    def test_requires_lineage(self) -> None:
        with self.assertRaises(ValueError):
            validate_derived_relationship(Relationship(
                relationship_id="rel_no_lineage",
                source_entity_id="a",
                target_entity_id="b",
                relationship_type="associated_with",
                semantic_class="derived",
                first_seen_at="2026-09-28T20:00:00Z",
                last_seen_at="2026-09-28T20:00:00Z",
            ))

    def test_persists_only_validated_derived_relationships(self) -> None:
        relationship = Relationship(
            relationship_id="rel_valid",
            source_entity_id="a",
            target_entity_id="b",
            relationship_type="associated_with",
            semantic_class="derived",
            first_seen_at="2026-09-28T20:00:00Z",
            last_seen_at="2026-09-28T21:00:00Z",
            valid_from="2026-09-20T00:00:00Z",
            confidence=0.65,
            derived_from=("claim_1",),
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "graph.db")
            try:
                self.assertEqual(1, persist_derived_relationships(store, [relationship]))
                rows = store.load_relationships()
                self.assertEqual("geowatch-temporal-graph-adapter", rows[0].derivation_method)
                self.assertEqual("v1", rows[0].derivation_version)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
