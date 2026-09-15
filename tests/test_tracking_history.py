from __future__ import annotations

import unittest

from geowatch.tracking_history import TrackHistory


class TrackHistoryTests(unittest.TestCase):
    def test_records_movement_and_skips_duplicate_noise(self) -> None:
        history = TrackHistory(max_entities=10, max_points_per_entity=4, min_interval_seconds=5, min_move_meters=20)
        self.assertTrue(history.record("abc", 0, 0, epoch=100, observed_at="t1"))
        self.assertFalse(history.record("abc", 0.00001, 0.00001, epoch=101, observed_at="t2"))
        self.assertTrue(history.record("abc", 0.01, 0.01, epoch=110, observed_at="t3"))
        rows = history.get("abc")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["observed_at"], "t1")
        self.assertEqual(rows[-1]["observed_at"], "t3")

    def test_per_entity_and_global_bounds_are_enforced(self) -> None:
        history = TrackHistory(max_entities=2, max_points_per_entity=3, min_interval_seconds=0, min_move_meters=0)
        for index in range(5):
            history.record("a", 0, index * 0.01, epoch=100 + index)
        self.assertEqual(len(history.get("a")), 3)
        history.record("b", 1, 1, epoch=200)
        history.record("c", 2, 2, epoch=300)
        self.assertEqual(history.entity_count(), 2)
        self.assertEqual(history.get("a"), [])

    def test_prune_and_validation(self) -> None:
        history = TrackHistory(max_entities=2, max_points_per_entity=3)
        history.record("a", 0, 0, epoch=100)
        history.record("b", 1, 1, epoch=190)
        self.assertEqual(history.prune(older_than_seconds=50, now_epoch=200), 1)
        self.assertEqual(history.get("a"), [])
        self.assertEqual(len(history.get("b")), 1)
        with self.assertRaises(ValueError):
            history.record("bad", 91, 0, epoch=201)
        with self.assertRaises(ValueError):
            history.get("b", limit=1)


if __name__ == "__main__":
    unittest.main()
