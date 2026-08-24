from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def _postgres(store) -> bool:
    return getattr(store, "backend", "sqlite") == "postgresql-postgis"


def ensure_tables(store) -> None:
    """Create v0.9 strategic-learning tables in the configured primary database."""
    if _postgres(store):
        sql = """
        CREATE TABLE IF NOT EXISTS review_decisions (
          decision_id TEXT PRIMARY KEY, review_id TEXT NOT NULL, episode_id TEXT NOT NULL,
          decided_at TIMESTAMPTZ NOT NULL, decision TEXT NOT NULL, rationale TEXT NOT NULL,
          reviewer TEXT, payload_json JSONB NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_review_decisions_episode ON review_decisions(episode_id, decided_at);
        CREATE TABLE IF NOT EXISTS episode_operations (
          operation_id TEXT PRIMARY KEY, operation_type TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
          status TEXT NOT NULL, source_episode_ids JSONB NOT NULL, target_episode_ids JSONB NOT NULL,
          reason TEXT NOT NULL, before_json JSONB, after_json JSONB, payload_json JSONB NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_episode_operations_at ON episode_operations(occurred_at);
        CREATE TABLE IF NOT EXISTS forecasts (
          forecast_id TEXT PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL, horizon_at TIMESTAMPTZ NOT NULL,
          subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, question TEXT NOT NULL,
          probability DOUBLE PRECISION NOT NULL, status TEXT NOT NULL DEFAULT 'open',
          outcome INTEGER, resolved_at TIMESTAMPTZ, rationale TEXT, payload_json JSONB NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_forecasts_subject ON forecasts(subject_type, subject_id, created_at);
        CREATE TABLE IF NOT EXISTS knowledge_proposals (
          proposal_id TEXT PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL, status TEXT NOT NULL,
          proposal_type TEXT NOT NULL, subject_id TEXT, rationale TEXT NOT NULL,
          source_decision_ids JSONB NOT NULL, payload_json JSONB NOT NULL
        );
        """
        with store.db.cursor() as cur:
            cur.execute(sql)
        store.db.commit()
        return

    store.db.executescript("""
    CREATE TABLE IF NOT EXISTS review_decisions (
      decision_id TEXT PRIMARY KEY, review_id TEXT NOT NULL, episode_id TEXT NOT NULL,
      decided_at TEXT NOT NULL, decision TEXT NOT NULL, rationale TEXT NOT NULL,
      reviewer TEXT, payload_json TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_review_decisions_episode ON review_decisions(episode_id, decided_at);
    CREATE TABLE IF NOT EXISTS episode_operations (
      operation_id TEXT PRIMARY KEY, operation_type TEXT NOT NULL, occurred_at TEXT NOT NULL,
      status TEXT NOT NULL, source_episode_ids TEXT NOT NULL, target_episode_ids TEXT NOT NULL,
      reason TEXT NOT NULL, before_json TEXT, after_json TEXT, payload_json TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_episode_operations_at ON episode_operations(occurred_at);
    CREATE TABLE IF NOT EXISTS forecasts (
      forecast_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, horizon_at TEXT NOT NULL,
      subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, question TEXT NOT NULL,
      probability REAL NOT NULL, status TEXT NOT NULL DEFAULT 'open', outcome INTEGER,
      resolved_at TEXT, rationale TEXT, payload_json TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_forecasts_subject ON forecasts(subject_type, subject_id, created_at);
    CREATE TABLE IF NOT EXISTS knowledge_proposals (
      proposal_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL,
      proposal_type TEXT NOT NULL, subject_id TEXT, rationale TEXT NOT NULL,
      source_decision_ids TEXT NOT NULL, payload_json TEXT NOT NULL
    );
    """)
    store.db.commit()


def record_review_decision(store, *, review_id: str, episode_id: str, decision: str, rationale: str,
                           reviewer: str | None = None, decided_at: str | None = None,
                           metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_tables(store)
    decided_at = decided_at or datetime.now(timezone.utc).isoformat()
    fingerprint = f"{review_id}|{episode_id}|{decision}|{decided_at}"
    decision_id = "rdec_" + hashlib.sha256(fingerprint.encode()).hexdigest()[:20]
    row = {"decision_id": decision_id, "review_id": review_id, "episode_id": episode_id,
           "decided_at": decided_at, "decision": decision, "rationale": rationale,
           "reviewer": reviewer, "metadata": metadata or {}}
    payload = json.dumps(row, ensure_ascii=False)
    if _postgres(store):
        with store.db.cursor() as cur:
            cur.execute("""INSERT INTO review_decisions(decision_id,review_id,episode_id,decided_at,decision,rationale,reviewer,payload_json)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT(decision_id) DO NOTHING""",
                        (decision_id, review_id, episode_id, decided_at, decision, rationale, reviewer, payload))
    else:
        store.db.execute("INSERT OR IGNORE INTO review_decisions VALUES(?,?,?,?,?,?,?,?)",
                         (decision_id, review_id, episode_id, decided_at, decision, rationale, reviewer, payload))
    store.db.commit()
    return row


def list_review_decisions(store, *, episode_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    ensure_tables(store)
    limit = max(1, min(limit, 2000))
    if _postgres(store):
        with store.db.cursor() as cur:
            if episode_id:
                cur.execute("SELECT payload_json FROM review_decisions WHERE episode_id=%s ORDER BY decided_at DESC LIMIT %s", (episode_id, limit))
            else:
                cur.execute("SELECT payload_json FROM review_decisions ORDER BY decided_at DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
        return [_as_dict(row["payload_json"]) for row in rows]
    if episode_id:
        rows = store.db.execute("SELECT payload_json FROM review_decisions WHERE episode_id=? ORDER BY decided_at DESC LIMIT ?", (episode_id, limit)).fetchall()
    else:
        rows = store.db.execute("SELECT payload_json FROM review_decisions ORDER BY decided_at DESC LIMIT ?", (limit,)).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def record_operation(store, *, operation_type: str, source_episode_ids: list[str], target_episode_ids: list[str],
                     reason: str, before: Any, after: Any, status: str = "applied",
                     occurred_at: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_tables(store)
    occurred_at = occurred_at or datetime.now(timezone.utc).isoformat()
    fingerprint = f"{operation_type}|{occurred_at}|{'|'.join(sorted(source_episode_ids))}|{'|'.join(sorted(target_episode_ids))}"
    operation_id = "op_" + hashlib.sha256(fingerprint.encode()).hexdigest()[:20]
    row = {"operation_id": operation_id, "operation_type": operation_type, "occurred_at": occurred_at,
           "status": status, "source_episode_ids": source_episode_ids, "target_episode_ids": target_episode_ids,
           "reason": reason, "before": before, "after": after, "metadata": metadata or {}}
    if _postgres(store):
        with store.db.cursor() as cur:
            cur.execute("""INSERT INTO episode_operations(operation_id,operation_type,occurred_at,status,source_episode_ids,target_episode_ids,reason,before_json,after_json,payload_json)
            VALUES(%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s::jsonb) ON CONFLICT(operation_id) DO NOTHING""",
                        (operation_id, operation_type, occurred_at, status, json.dumps(source_episode_ids), json.dumps(target_episode_ids), reason,
                         json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False), json.dumps(row, ensure_ascii=False)))
    else:
        store.db.execute("INSERT OR IGNORE INTO episode_operations VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (operation_id, operation_type, occurred_at, status, json.dumps(source_episode_ids), json.dumps(target_episode_ids), reason,
                          json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False), json.dumps(row, ensure_ascii=False)))
    store.db.commit()
    return row


def list_operations(store, *, limit: int = 200) -> list[dict[str, Any]]:
    ensure_tables(store)
    limit = max(1, min(limit, 2000))
    if _postgres(store):
        with store.db.cursor() as cur:
            cur.execute("SELECT payload_json FROM episode_operations ORDER BY occurred_at DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
        return [_as_dict(row["payload_json"]) for row in rows]
    rows = store.db.execute("SELECT payload_json FROM episode_operations ORDER BY occurred_at DESC LIMIT ?", (limit,)).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def record_forecast(store, *, subject_type: str, subject_id: str, question: str, probability: float,
                    horizon_at: str, rationale: str = "", created_at: str | None = None,
                    metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be between 0 and 1")
    ensure_tables(store)
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    forecast_id = "fc_" + hashlib.sha256(f"{subject_type}|{subject_id}|{question}|{created_at}".encode()).hexdigest()[:20]
    row = {"forecast_id": forecast_id, "created_at": created_at, "horizon_at": horizon_at,
           "subject_type": subject_type, "subject_id": subject_id, "question": question,
           "probability": probability, "status": "open", "outcome": None,
           "resolved_at": None, "rationale": rationale, "metadata": metadata or {}}
    payload = json.dumps(row, ensure_ascii=False)
    if _postgres(store):
        with store.db.cursor() as cur:
            cur.execute("""INSERT INTO forecasts(forecast_id,created_at,horizon_at,subject_type,subject_id,question,probability,status,rationale,payload_json)
            VALUES(%s,%s,%s,%s,%s,%s,%s,'open',%s,%s::jsonb) ON CONFLICT(forecast_id) DO NOTHING""",
                        (forecast_id, created_at, horizon_at, subject_type, subject_id, question, probability, rationale, payload))
    else:
        store.db.execute("""INSERT OR IGNORE INTO forecasts(forecast_id,created_at,horizon_at,subject_type,subject_id,question,probability,status,rationale,payload_json)
        VALUES(?,?,?,?,?,?,?,'open',?,?)""", (forecast_id, created_at, horizon_at, subject_type, subject_id, question, probability, rationale, payload))
    store.db.commit()
    return row


def resolve_forecast(store, forecast_id: str, *, outcome: bool, resolved_at: str | None = None, rationale: str = "") -> dict[str, Any]:
    ensure_tables(store)
    resolved_at = resolved_at or datetime.now(timezone.utc).isoformat()
    current = get_forecast(store, forecast_id)
    if current is None:
        raise KeyError(forecast_id)
    current.update({"status": "resolved", "outcome": 1 if outcome else 0, "resolved_at": resolved_at,
                    "resolution_rationale": rationale})
    payload = json.dumps(current, ensure_ascii=False)
    if _postgres(store):
        with store.db.cursor() as cur:
            cur.execute("UPDATE forecasts SET status='resolved',outcome=%s,resolved_at=%s,payload_json=%s::jsonb WHERE forecast_id=%s",
                        (1 if outcome else 0, resolved_at, payload, forecast_id))
    else:
        store.db.execute("UPDATE forecasts SET status='resolved',outcome=?,resolved_at=?,payload_json=? WHERE forecast_id=?",
                         (1 if outcome else 0, resolved_at, payload, forecast_id))
    store.db.commit()
    return current


def get_forecast(store, forecast_id: str) -> dict[str, Any] | None:
    ensure_tables(store)
    if _postgres(store):
        with store.db.cursor() as cur:
            cur.execute("SELECT payload_json FROM forecasts WHERE forecast_id=%s", (forecast_id,))
            row = cur.fetchone()
        return _as_dict(row["payload_json"]) if row else None
    row = store.db.execute("SELECT payload_json FROM forecasts WHERE forecast_id=?", (forecast_id,)).fetchone()
    return json.loads(row["payload_json"]) if row else None


def list_forecasts(store, *, status: str | None = None, limit: int = 5000) -> list[dict[str, Any]]:
    ensure_tables(store)
    limit = max(1, min(limit, 20000))
    if _postgres(store):
        with store.db.cursor() as cur:
            if status:
                cur.execute("SELECT payload_json FROM forecasts WHERE status=%s ORDER BY created_at LIMIT %s", (status, limit))
            else:
                cur.execute("SELECT payload_json FROM forecasts ORDER BY created_at LIMIT %s", (limit,))
            rows = cur.fetchall()
        return [_as_dict(row["payload_json"]) for row in rows]
    if status:
        rows = store.db.execute("SELECT payload_json FROM forecasts WHERE status=? ORDER BY created_at LIMIT ?", (status, limit)).fetchall()
    else:
        rows = store.db.execute("SELECT payload_json FROM forecasts ORDER BY created_at LIMIT ?", (limit,)).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def record_knowledge_proposal(store, *, proposal_type: str, rationale: str, source_decision_ids: list[str],
                              subject_id: str | None = None, payload: dict[str, Any] | None = None,
                              created_at: str | None = None) -> dict[str, Any]:
    ensure_tables(store)
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    proposal_id = "kp_" + hashlib.sha256(f"{proposal_type}|{subject_id}|{created_at}|{'|'.join(source_decision_ids)}".encode()).hexdigest()[:20]
    row = {"proposal_id": proposal_id, "created_at": created_at, "status": "proposed",
           "proposal_type": proposal_type, "subject_id": subject_id, "rationale": rationale,
           "source_decision_ids": source_decision_ids, "payload": payload or {}}
    encoded = json.dumps(row, ensure_ascii=False)
    if _postgres(store):
        with store.db.cursor() as cur:
            cur.execute("""INSERT INTO knowledge_proposals(proposal_id,created_at,status,proposal_type,subject_id,rationale,source_decision_ids,payload_json)
            VALUES(%s,%s,'proposed',%s,%s,%s,%s::jsonb,%s::jsonb) ON CONFLICT(proposal_id) DO NOTHING""",
                        (proposal_id, created_at, proposal_type, subject_id, rationale, json.dumps(source_decision_ids), encoded))
    else:
        store.db.execute("INSERT OR IGNORE INTO knowledge_proposals VALUES(?,?,?,?,?,?,?,?)",
                         (proposal_id, created_at, "proposed", proposal_type, subject_id, rationale, json.dumps(source_decision_ids), encoded))
    store.db.commit()
    return row


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)
