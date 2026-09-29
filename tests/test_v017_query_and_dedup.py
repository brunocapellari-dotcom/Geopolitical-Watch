from __future__ import annotations

import unittest

from geowatch.deduplication import canonicalize_url, duplicate_reason, fingerprint_content, text_similarity
from geowatch.epistemics import classify_event, evidence_confidence_proxy
from geowatch.event_query import filter_event_records
from geowatch.models import Event


def _event(**changes):
    values = dict(
        event_id="evt-1",
        source_id="source-1",
        source_kind="news",
        title="Reported drone strike near port",
        event_type="drone_strike",
        reference_at="2026-09-29T10:00:00+00:00",
        collected_at="2026-09-29T10:01:00+00:00",
        verification_level="osint_signal",
        country="Example",
        region="North Coast",
        actors=("Example Force",),
        source_url="https://example.com/a",
    )
    values.update(changes)
    return Event(**values)


class V017QueryDedupTests(unittest.TestCase):
    def test_canonical_url_removes_tracking_and_sorts_query(self) -> None:
        value = canonicalize_url("HTTPS://Example.COM/a/?utm_source=x&b=2&a=1#fragment")
        self.assertEqual("https://example.com/a?a=1&b=2", value)

    def test_dedup_fingerprints_raw_normalized_and_near_text(self) -> None:
        left = fingerprint_content(b"a", text="Strike reported near port", url="https://x.test/a?utm_source=z")
        right = fingerprint_content(b"b", text="Strike reported near the port", url="https://x.test/a")
        self.assertEqual("canonical_url_match", duplicate_reason(left, right))
        self.assertGreater(text_similarity("alpha beta gamma", "alpha beta gamma delta"), 0.7)

    def test_epistemic_classification_is_explicit(self) -> None:
        event = _event()
        self.assertEqual("NAO_CONFIRMADO", classify_event(event))
        self.assertLess(evidence_confidence_proxy(event), 0.6)
        sensor = _event(verification_level="sensor_signal")
        self.assertEqual("OBSERVADO", classify_event(sensor))

    def test_event_filters_cover_region_actor_type_epistemic_confidence(self) -> None:
        event = _event()
        rows = filter_event_records(
            [event],
            region="north",
            actor="example force",
            event_type="drone_strike",
            epistemic_state="NAO_CONFIRMADO",
            min_confidence=0.4,
        )
        self.assertEqual(1, len(rows))
        self.assertIn("evidence_confidence_proxy", rows[0])
        self.assertEqual([], filter_event_records([event], actor="other force"))


if __name__ == "__main__":
    unittest.main()
