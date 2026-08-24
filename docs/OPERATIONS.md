# Operations contract

## Production topology

Recommended topology:

1. Cloud Run service: read-only HTTP/API and dashboard layer.
2. Cloud Run job: collection, normalization, convergence, reports and alert generation.
3. Cloud Scheduler: invokes the collector job on the configured cadence.
4. PostgreSQL + PostGIS: durable normalized events, entities, claims, episodes, lineage, reports and outbox.
5. Google Cloud Storage: immutable/content-addressed RAW payloads.
6. Secret Manager: database DSN, API token and optional source credentials.

SQLite and filesystem RAW remain the local development/reference path.

## Required production settings

- `GEOWATCH_DB_URL=postgresql://...`
- `GEOWATCH_RAW_BUCKET=<bucket>`
- `GEOWATCH_API_TOKEN=<secret>`

Source credentials remain opt-in and must only be mounted when the corresponding source is enabled.

## Health and observability

- `/health` verifies process availability and identifies the selected storage backend.
- `/v2/operational` exposes JSON operational counters.
- `/metrics` exposes Prometheus text metrics.
- `collector_runs` preserves source-level success/error history and record counts.
- `source_checkpoints` preserves incremental progress.
- `episode_changes` is the durable change lineage.
- `alert_outbox` provides retryable delivery state for the product layer.

## Initial SLO targets

These are engineering targets, not claims about a deployment that has not yet been observed:

- API availability target: 99.5% monthly during the pre-1.0 phase.
- GDELT/GDACS collection freshness target: successful collection within 2 hours.
- Collector failure detection target: surface source error within one scheduled run.
- RAW durability target: every successfully parsed production payload has a content-addressed GCS object reference.
- Database backup target: automated daily backup plus point-in-time recovery where the managed database supports it.

## Backup and disaster recovery

Production database provisioning should enable automated backups and point-in-time recovery before the first sustained collection. RAW objects are content-addressed and should use bucket versioning/retention according to cost and source-term requirements. Recovery drills should validate: database restore, API read path, checkpoint integrity and one collector replay.

## Security

- Keep the repository private until redistribution/source-rights review is complete.
- Never commit API tokens, passwords or DSNs.
- API service should require Cloud Run IAM and/or `GEOWATCH_API_TOKEN`.
- Collector service account should receive only secret access, object write/read for its RAW bucket, and database connectivity needed for its task.
- Scheduler should only receive permission to invoke the collector job.
- Do not expose full copyrighted news bodies in reports or feeds.

## Deployment gate

`scripts/deploy_gcp.sh` is a reproducible deployment helper. Production is only considered live after all of the following are verified in the target GCP project:

1. PostgreSQL/PostGIS connection succeeds and migrations apply.
2. GCS RAW object is written by a collector execution.
3. Manual Cloud Run job exits successfully.
4. `/health`, `/v2/feed`, `/v2/episodes` and `/metrics` return expected authenticated responses.
5. Scheduler triggers at least one successful job.
6. Backup/PITR policy is enabled for the production database.

Until those checks occur, the repository is deployment-ready but not a verified 24/7 deployment.
