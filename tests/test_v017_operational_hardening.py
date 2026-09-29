from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from geowatch.circuit_breaker import CircuitBreaker
from geowatch.contracts import EventContract, json_schema_bundle
from geowatch.evidence_ledger import build_entry, deterministic_ledger_id
from geowatch.migrations import validate_migration_contract
from geowatch.models import Event
from geowatch.project_registry import load_project_registry
from geowatch.settings import GeoWatchSettings
from geowatch.stix_boundary import export_bundle, import_boundary


class V017OperationalHardeningTests(unittest.TestCase):
    def test_settings_validate_bounds_and_strict_contract(self) -> None:
        settings = GeoWatchSettings(
            GEOWATCH_DB_URL="postgresql://user:pass@db/geowatch",
            GEOWATCH_RAW_BACKEND="postgres",
            GEOWATCH_API_TOKEN="x" * 32,
            GEOWATCH_EXTERNAL_SCHEDULER=True,
            GEOWATCH_SOURCE_SCHEDULER=False,
            GEOWATCH_STRICT_PRODUCTION=True,
        )
        self.assertTrue(all(settings.validate_startup().values()))
        with self.assertRaises(ValidationError):
            GeoWatchSettings(GEOWATCH_SOURCE_SCHEDULER_TICK=1)

    def test_json_schema_bundle_contains_canonical_contracts(self) -> None:
        bundle = json_schema_bundle()
        self.assertEqual("https://json-schema.org/draft/2020-12/schema", bundle["$schema"])
        contracts = bundle["contracts"]
        for name in ("Source", "Observation", "Evidence", "Claim", "Location", "Actor", "Event", "Conflict"):
            self.assertIn(name, contracts)
        model = EventContract(
            event_id="evt-1",
            event_type="airstrike",
            title="Reported strike",
            reference_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
            epistemic_class="RELATADO",
        )
        self.assertEqual("evt-1", model.event_id)

    def test_project_registry_has_unique_services_and_required_gates(self) -> None:
        registry = load_project_registry()
        self.assertEqual("geopolitical-watch", registry.project_id)
        self.assertTrue(registry.required_gates)
        self.assertEqual(len(registry.services), len({row.service_id for row in registry.services}))

    def test_migration_contract_registers_version_and_tables(self) -> None:
        names = validate_migration_contract()
        self.assertIn("005_operational_hardening.sql", names)
        text = Path("sql/migrations/005_operational_hardening.sql").read_text(encoding="utf-8").casefold()
        for table in ("source_runtime_state", "collector_dead_letter", "evidence_ledger", "claim_revisions"):
            self.assertIn(f"create table if not exists {table}", text)

    def test_evidence_ledger_is_deterministic_and_validates_sha(self) -> None:
        one = deterministic_ledger_id(source_id="x", raw_ref="raw", evidence_id="e1", event_id="v1")
        two = deterministic_ledger_id(source_id="x", raw_ref="raw", evidence_id="e1", event_id="v1")
        self.assertEqual(one, two)
        entry = build_entry(source_id="x", raw_ref="raw", raw_sha256="a" * 64)
        self.assertEqual("a" * 64, entry.raw_sha256)
        with self.assertRaises(ValueError):
            build_entry(source_id="x", raw_ref="raw", raw_sha256="bad")

    def test_circuit_breaker_opens_and_recovers(self) -> None:
        breaker = CircuitBreaker(failure_threshold=2, recovery_seconds=60)
        now = datetime(2026, 9, 29, tzinfo=timezone.utc)
        breaker.record_failure(now=now)
        self.assertTrue(breaker.allow_request(now=now))
        breaker.record_failure(now=now)
        self.assertFalse(breaker.allow_request(now=now))
        breaker.record_success(now=now)
        self.assertTrue(breaker.allow_request(now=now))
        self.assertEqual(0, breaker.snapshot(now=now)["consecutive_failures"])

    def test_stix_boundary_roundtrip_preserves_geowatch_identity(self) -> None:
        event = Event(
            event_id="evt-1",
            source_id="source-1",
            source_kind="news",
            title="Reported strike",
            event_type="airstrike",
            reference_at="2026-09-29T10:00:00+00:00",
            collected_at="2026-09-29T10:01:00+00:00",
            verification_level="osint_signal",
        )
        bundle = export_bundle(events=[event])
        imported = import_boundary(bundle)
        self.assertEqual(1, len(imported["events"]))
        self.assertEqual("evt-1", imported["events"][0]["x_geowatch_event_id"])

    def test_event_taxonomy_has_unique_ids(self) -> None:
        payload = json.loads(Path("config/event_taxonomy.json").read_text(encoding="utf-8"))
        ids = [row["id"] for row in payload["event_types"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("drone_strike", ids)
        self.assertIn("ceasefire", ids)


if __name__ == "__main__":
    unittest.main()
