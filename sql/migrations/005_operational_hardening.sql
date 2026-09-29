CREATE TABLE IF NOT EXISTS source_runtime_state (
  source_id TEXT PRIMARY KEY,
  operational_state TEXT NOT NULL,
  last_success_at TIMESTAMPTZ,
  last_failure_at TIMESTAMPTZ,
  consecutive_failures INTEGER NOT NULL DEFAULT 0,
  circuit_open_until TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_source_runtime_state_state
  ON source_runtime_state(operational_state, updated_at DESC);

CREATE TABLE IF NOT EXISTS collector_dead_letter (
  dead_letter_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  failed_at TIMESTAMPTZ NOT NULL,
  failure_class TEXT NOT NULL,
  error_type TEXT,
  error_message TEXT,
  request_json JSONB,
  payload_ref TEXT,
  attempts INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'pending',
  replayed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_collector_dead_letter_pending
  ON collector_dead_letter(status, failed_at DESC);
CREATE INDEX IF NOT EXISTS idx_collector_dead_letter_source
  ON collector_dead_letter(source_id, failed_at DESC);

CREATE TABLE IF NOT EXISTS evidence_ledger (
  ledger_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  raw_ref TEXT,
  raw_sha256 TEXT,
  extraction_id TEXT,
  evidence_id TEXT,
  claim_id TEXT,
  event_id TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_evidence_ledger_source
  ON evidence_ledger(source_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_ledger_claim
  ON evidence_ledger(claim_id) WHERE claim_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_evidence_ledger_event
  ON evidence_ledger(event_id) WHERE event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_evidence_ledger_raw_sha
  ON evidence_ledger(raw_sha256) WHERE raw_sha256 IS NOT NULL;

CREATE TABLE IF NOT EXISTS claim_revisions (
  revision_id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL,
  confidence DOUBLE PRECISION,
  supersedes_claim_id TEXT,
  claim_json JSONB NOT NULL,
  UNIQUE(claim_id, revision)
);
CREATE INDEX IF NOT EXISTS idx_claim_revisions_claim
  ON claim_revisions(claim_id, revision DESC);

INSERT INTO schema_migrations(version, name)
VALUES (5, 'v0.17 operational hardening')
ON CONFLICT(version) DO NOTHING;
