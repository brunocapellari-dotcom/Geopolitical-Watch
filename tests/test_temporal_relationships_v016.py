from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from geowatch.models import Relationship
from geowatch.storage import SQLiteStore


class TemporalRelationshipTests(unittest.TestCase):
    def test_relationship_roundtrip_preserves_observation_and_validity_time(self) -> None:
        relationship = Relationship(
            relationship_id="rel_1",
            source_entity_id="actor_a",
            target_entity_id="port_b",
            relationship_type="controls",
            semantic_class="derived",
            first_seen_at="2026-09-20T10:00:00Z",
            last_seen_at="2026-09-28T12:00:00Z",
            valid_from="2026-09-18T00:00:00Z",
            valid_to=None,
            confidence=0.72,
            source_quality=0.9,
            derivation_method="temporal-graph-adapter",
            derivation_version="v1",
            evidence_ids=("ev_1", "ev_2"),
            source_ids=("src_1",),
            contradicts=("rel_0",),
            supersedes=(),
            derived_from=("claim_1",),
            provenance={"raw_ref": "pgraw://src/hash", "method_version": "v1"},
        )

        restored = Relationship.from_dict(relationship.to_dict())

        self.assertEqual(relationship, restored)
        self.assertNotEqual(restored.first_seen_at, restored.valid_from)
        self.assertEqual("derived", restored.semantic_class)


    def test_relationship_rejects_invalid_time_and_confidence(self) -> None:
        with self.assertRaises(ValueError):
            Relationship(
                relationship_id="rel_bad_time",
                source_entity_id="a",
                target_entity_id="b",
                relationship_type="test",
                semantic_class="derived",
                first_seen_at="2026-09-28T12:00:00Z",
                last_seen_at="2026-09-28T11:00:00Z",
            )
        with self.assertRaises(ValueError):
            Relationship(
                relationship_id="rel_bad_confidence",
                source_entity_id="a",
                target_entity_id="b",
                relationship_type="test",
                semantic_class="derived",
                first_seen_at="2026-09-28T11:00:00Z",
                last_seen_at="2026-09-28T12:00:00Z",
                confidence=1.1,
            )

    def test_sqlite_relationship_storage_and_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "geowatch.db")
            try:
                relationships = [
                    Relationship(
                        relationship_id="rel_a",
                        source_entity_id="entity_1",
                        target_entity_id="entity_2",
                        relationship_type="supports",
                        semantic_class="reported",
                        first_seen_at="2026-09-27T00:00:00Z",
                        last_seen_at="2026-09-28T00:00:00Z",
                        evidence_ids=("evidence_1",),
                        source_ids=("source_1",),
                    ),
                    Relationship(
                        relationship_id="rel_b",
                        source_entity_id="entity_3",
                        target_entity_id="entity_1",
                        relationship_type="located_at",
                        semantic_class="observed",
                        first_seen_at="2026-09-26T00:00:00Z",
                        last_seen_at="2026-09-28T01:00:00Z",
                        valid_from="2026-09-26T00:00:00Z",
                    ),
                ]

                self.assertEqual(2, store.upsert_relationships(relationships))
                entity_rows = store.load_relationships(entity_id="entity_1")
                self.assertEqual({"rel_a", "rel_b"}, {row.relationship_id for row in entity_rows})

                type_rows = store.load_relationships(relationship_type="supports")
                self.assertEqual(["rel_a"], [row.relationship_id for row in type_rows])
                self.assertEqual(("evidence_1",), type_rows[0].evidence_ids)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
