from __future__ import annotations

import json
import tempfile
from pathlib import Path

from geowatch.learning import learning_policy
from geowatch.pipeline import run
from geowatch.storage_factory import open_store


def _snapshot(db_path: Path) -> dict[str, object]:
    store = open_store(db_path)
    try:
        events = store.load_events_since("1970-01-01T00:00:00+00:00")
        claims = store.load_claims()
        evidence = store.load_evidence()
        episodes = store.load_episodes(since="1970-01-01T00:00:00+00:00")
        runs = store.recent_runs(limit=100)
        evidence_ids = {row.evidence_id for row in evidence}
        dangling_claim_evidence = sorted(
            {
                evidence_id
                for claim in claims
                for evidence_id in claim.evidence_ids
                if evidence_id not in evidence_ids
            }
        )
        return {
            "events": len(events),
            "event_ids": sorted(row.event_id for row in events),
            "claims": len(claims),
            "claim_ids": sorted(row.claim_id for row in claims),
            "evidence": len(evidence),
            "evidence_ids": sorted(evidence_ids),
            "episodes": len(episodes),
            "episode_ids": sorted(row.episode_id for row in episodes),
            "collector_runs": len(runs),
            "successful_runs": sum(1 for row in runs if row.get("status") == "ok"),
            "failed_runs": sum(1 for row in runs if row.get("status") != "ok"),
            "dangling_claim_evidence": dangling_claim_evidence,
        }
    finally:
        store.close()


def main() -> int:
    output_dir = Path("audit-output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "autonomous-learning-audit.json"

    with tempfile.TemporaryDirectory(prefix="geowatch-learning-audit-") as temp_dir:
        root = Path(temp_dir)
        db_path = root / "audit.db"
        raw_root = root / "raw"
        reports_root = root / "reports"

        # Use the existing public-beta collectors unchanged. The probe is fully
        # isolated: no production DB, no production vault, and no repository write-back.
        first_run = run(
            config_path="config/sources.public-beta.json",
            db_path=db_path,
            raw_root=raw_root,
            reports_root=reports_root,
        )
        first = _snapshot(db_path)

        # A second live pass exercises checkpoint/update behavior and idempotent upserts.
        second_run = run(
            config_path="config/sources.public-beta.json",
            db_path=db_path,
            raw_root=raw_root,
            reports_root=reports_root,
        )
        second = _snapshot(db_path)

        # Close/reopen retrieval is intentional: it proves durable retrieval rather
        # than returning objects left in memory by the pipeline.
        reopened = _snapshot(db_path)
        raw_files = [path for path in raw_root.rglob("*") if path.is_file()]

        policy = learning_policy()
        collection_ok = (
            first["successful_runs"] >= 1
            and first["events"] >= 1
            and len(raw_files) >= 1
        )
        interpretation_ok = first["episodes"] >= 1 and first["claims"] >= 1
        evidence_ok = first["evidence"] >= 1 and not first["dangling_claim_evidence"]
        durable_retrieval_ok = (
            second["claim_ids"] == reopened["claim_ids"]
            and second["evidence_ids"] == reopened["evidence_ids"]
            and second["episode_ids"] == reopened["episode_ids"]
        )
        update_ok = (
            second["collector_runs"] > first["collector_runs"]
            and second["events"] >= first["events"]
            and second["claims"] >= first["claims"]
        )
        canonical_autonomy_enabled = bool(policy.get("auto_mutate_knowledge"))

        result = {
            "schema_version": "second-brain-autonomous-learning-functional-audit-v1",
            "scope": "existing Geopolitical-Watch autonomous ingestion/claim/evidence stack",
            "isolation": {
                "production_database_touched": False,
                "production_vault_touched": False,
                "repository_writeback": False,
                "live_external_sources_used": True,
            },
            "first_run": first_run,
            "second_run": second_run,
            "first_snapshot": first,
            "second_snapshot": second,
            "reopened_snapshot": reopened,
            "raw_artifact_files": len(raw_files),
            "gates": {
                "collect": collection_ok,
                "interpret": interpretation_ok,
                "claims_and_evidence": evidence_ok,
                "automatic_update_cycle": update_ok,
                "durable_retrieval_after_reopen": durable_retrieval_ok,
                "canonical_autonomous_learning": canonical_autonomy_enabled,
            },
            "learning_policy": policy,
            "verdict": (
                "END_TO_END_CANONICAL_PROVEN"
                if all(
                    [
                        collection_ok,
                        interpretation_ok,
                        evidence_ok,
                        update_ok,
                        durable_retrieval_ok,
                        canonical_autonomy_enabled,
                    ]
                )
                else "PARTIAL_NOT_END_TO_END_CANONICAL"
            ),
            "blocking_gap": (
                None
                if canonical_autonomy_enabled
                else "Existing policy explicitly forbids automatic canonical knowledge mutation."
            ),
        }
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # Fail only if the existing executable ingestion/claim/evidence/retrieval path is
    # broken. A governance decision that canonical promotion is non-automatic is an
    # audit finding, not a test-infrastructure failure.
    return 0 if all([collection_ok, interpretation_ok, evidence_ok, update_ok, durable_retrieval_ok]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
