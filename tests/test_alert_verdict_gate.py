from __future__ import annotations

import unittest

from geowatch.alerts import AlertPolicy, evaluate_alerts
from geowatch.models import ConflictEpisode, EvidenceStrength
from geowatch.verdict import VerdictResult


def episode() -> ConflictEpisode:
    return ConflictEpisode(
        episode_id="ep1", title="Example escalation", state="escalating",
        started_at="2026-09-15T00:00:00+00:00", last_updated_at="2026-09-15T01:00:00+00:00",
        countries=("ZZ",), regions=(), event_ids=("e1",), claim_ids=("c1",), evidence_ids=("x1",),
        evidence_strength=EvidenceStrength(0.8, 0.0, 0.7, 0.0, 0.7, 0.7, 0.9, 0.0, 70),
    )


class AlertVerdictGateTests(unittest.TestCase):
    def test_high_alert_is_suppressed_when_claim_is_unverified(self) -> None:
        policy = AlertPolicy(
            policy_id="high", severity="high", states=("escalating",), min_strength=30,
            allowed_verdicts=("CONFIRMADO", "PROVÁVEL"), min_verdict_confidence=58,
        )
        verdict = VerdictResult("c1", "NÃO VERIFICADO", 40, "v", {}, ())
        self.assertEqual(evaluate_alerts([episode()], [], [policy], claim_verdicts={"c1": verdict}), [])

    def test_high_alert_passes_with_probable_claim(self) -> None:
        policy = AlertPolicy(
            policy_id="high", severity="high", states=("escalating",), min_strength=30,
            allowed_verdicts=("CONFIRMADO", "PROVÁVEL"), min_verdict_confidence=58,
        )
        verdict = VerdictResult("c1", "PROVÁVEL", 66, "v", {}, ("corroborated",))
        rows = evaluate_alerts([episode()], [], [policy], claim_verdicts={"c1": verdict})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["schema_version"], "geowatch-alert-v2")
        self.assertEqual(rows[0]["claim_verdicts"][0]["verdict"], "PROVÁVEL")

    def test_material_alert_is_suppressed_when_all_supporting_sources_are_stale(self) -> None:
        policy = AlertPolicy(
            policy_id="high", severity="high", states=("escalating",), min_strength=30,
            allowed_verdicts=("CONFIRMADO", "PROVÁVEL"), min_verdict_confidence=58,
            require_operational_source_health=True,
        )
        verdict = VerdictResult("c1", "PROVÁVEL", 66, "v", {}, ("corroborated",))
        rows = evaluate_alerts(
            [episode()],
            [],
            [policy],
            claim_verdicts={"c1": verdict},
            claim_source_ids={"c1": ("source-a", "source-b")},
            source_health={"source-a": "stale", "source-b": "inactive"},
        )
        self.assertEqual(rows, [])

    def test_material_alert_passes_when_one_supporting_source_is_operational(self) -> None:
        policy = AlertPolicy(
            policy_id="high", severity="high", states=("escalating",), min_strength=30,
            allowed_verdicts=("CONFIRMADO", "PROVÁVEL"), min_verdict_confidence=58,
            require_operational_source_health=True,
        )
        verdict = VerdictResult("c1", "CONFIRMADO", 84, "v", {}, ("corroborated",))
        rows = evaluate_alerts(
            [episode()],
            [],
            [policy],
            claim_verdicts={"c1": verdict},
            claim_source_ids={"c1": ("source-a", "source-b")},
            source_health={"source-a": "stale", "source-b": "healthy"},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_health_gate"], "required")
        self.assertIn("source_health=operational", rows[0]["reason"])

    def test_health_required_policy_fails_closed_when_health_context_is_missing(self) -> None:
        policy = AlertPolicy(
            policy_id="high", severity="high", states=("escalating",), min_strength=30,
            allowed_verdicts=("PROVÁVEL",), min_verdict_confidence=58,
            require_operational_source_health=True,
        )
        verdict = VerdictResult("c1", "PROVÁVEL", 66, "v", {}, ())
        self.assertEqual(
            evaluate_alerts([episode()], [], [policy], claim_verdicts={"c1": verdict}),
            [],
        )


if __name__ == "__main__":
    unittest.main()
