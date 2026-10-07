CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  reference_at TIMESTAMPTZ NOT NULL,
  source_id TEXT NOT NULL,
  verification_level TEXT NOT NULL,
  country TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  geom geography(POINT,4326),
  event_json JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_reference ON events(reference_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_country ON events(country);
CREATE INDEX IF NOT EXISTS idx_events_geom ON events USING GIST(geom);

CREATE TABLE IF NOT EXISTS clusters (
  cluster_id TEXT PRIMARY KEY,
  generated_at TIMESTAMPTZ NOT NULL,
  priority_score INTEGER NOT NULL,
  cluster_json JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reports (
  report_id TEXT PRIMARY KEY,
  generated_at TIMESTAMPTZ NOT NULL,
  report_type TEXT NOT NULL,
  report_json JSONB NOT NULL,
  report_markdown TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reports_type_generated ON reports(report_type, generated_at DESC);

CREATE TABLE IF NOT EXISTS source_checkpoints (
  source_id TEXT PRIMARY KEY,
  last_success_at TIMESTAMPTZ,
  last_reference_at TIMESTAMPTZ,
  cursor_json JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS collector_runs (
  run_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL,
  records INTEGER NOT NULL DEFAULT 0,
  request_json JSONB,
  error TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_runs_source_started ON collector_runs(source_id, started_at DESC);

CREATE TABLE IF NOT EXISTS raw_artifacts (
  artifact_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  collected_at TIMESTAMPTZ NOT NULL,
  observed_url TEXT,
  path TEXT NOT NULL,
  bytes BIGINT NOT NULL,
  UNIQUE(source_id, sha256)
);

CREATE TABLE IF NOT EXISTS entities (
  entity_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  canonical_name TEXT NOT NULL,
  country TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  geom geography(POINT,4326),
  entity_json JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(canonical_name);
CREATE INDEX IF NOT EXISTS idx_entities_country ON entities(country);
CREATE INDEX IF NOT EXISTS idx_entities_geom ON entities USING GIST(geom);

CREATE TABLE IF NOT EXISTS relationships (
  relationship_id TEXT PRIMARY KEY,
  source_entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
  target_entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL,
  semantic_class TEXT NOT NULL,
  first_seen_at TIMESTAMPTZ NOT NULL,
  last_seen_at TIMESTAMPTZ NOT NULL,
  valid_from TIMESTAMPTZ,
  valid_to TIMESTAMPTZ,
  confidence DOUBLE PRECISION,
  relationship_json JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_relationships_validity ON relationships(valid_from, valid_to);

CREATE TABLE IF NOT EXISTS episodes (
  episode_id TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  last_updated_at TIMESTAMPTZ NOT NULL,
  primary_country TEXT,
  evidence_strength_index INTEGER,
  episode_json JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_episodes_state_updated ON episodes(state, last_updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_episodes_country ON episodes(primary_country);
CREATE INDEX IF NOT EXISTS idx_episodes_strength ON episodes(evidence_strength_index DESC);

CREATE TABLE IF NOT EXISTS episode_events (
  episode_id TEXT NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
  event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  linked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(episode_id, event_id)
);

CREATE TABLE IF NOT EXISTS claims (
  claim_id TEXT PRIMARY KEY,
  episode_id TEXT NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
  claim_type TEXT NOT NULL,
  topic_key TEXT NOT NULL,
  status TEXT NOT NULL,
  first_seen_at TIMESTAMPTZ NOT NULL,
  last_seen_at TIMESTAMPTZ NOT NULL,
  claim_json JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_claims_episode ON claims(episode_id);
CREATE INDEX IF NOT EXISTS idx_claims_topic ON claims(topic_key);

CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  source_id TEXT NOT NULL,
  verification_level TEXT NOT NULL,
  relation TEXT NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  evidence_json JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_evidence_event ON evidence(event_id);
CREATE INDEX IF NOT EXISTS idx_evidence_observed ON evidence(observed_at DESC);

CREATE TABLE IF NOT EXISTS claim_evidence (
  claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
  evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id) ON DELETE CASCADE,
  PRIMARY KEY(claim_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS episode_changes (
  change_id BIGSERIAL PRIMARY KEY,
  episode_id TEXT NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
  occurred_at TIMESTAMPTZ NOT NULL,
  change_type TEXT NOT NULL,
  change_json JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_changes_episode ON episode_changes(episode_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_changes_at ON episode_changes(occurred_at DESC);

CREATE TABLE IF NOT EXISTS object_versions (
  version_id BIGSERIAL PRIMARY KEY,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  payload_sha256 TEXT NOT NULL,
  payload_json JSONB NOT NULL,
  UNIQUE(object_type, object_id, payload_sha256)
);
CREATE INDEX IF NOT EXISTS idx_object_versions_asof ON object_versions(object_type, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_object_versions_object ON object_versions(object_type, object_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS alert_outbox (
  alert_id TEXT PRIMARY KEY,
  episode_id TEXT NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL,
  severity TEXT NOT NULL,
  policy_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  payload_json JSONB NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_alert_outbox_status ON alert_outbox(status, created_at);

INSERT INTO schema_migrations(version, name) VALUES
  (1, 'v0.4 baseline'),
  (2, 'v0.5 episode convergence'),
  (3, 'v0.6 postgres postgis operational layer'),
  (4, 'v0.16 temporal relationships'),
  (5, 'go-live immutable object versions')
ON CONFLICT(version) DO NOTHING;
