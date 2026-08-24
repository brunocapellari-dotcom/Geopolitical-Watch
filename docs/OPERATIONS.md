# Operations contract

## Production topology

Recommended topology:

1. Cloud Run service: read-only HTTP/API and dashboard shell.
2. Cloud Run collector job: collection, normalization, convergence, reports and alert generation.
3. Cloud Run alert-dispatch job: delivers pending outbox alerts to an optional external webhook.
4. Cloud Scheduler: invokes collector and, when configured, dispatcher jobs.
5. PostgreSQL + PostGIS: durable normalized events, entities, claims, episodes, lineage, reports and alert outbox.
6. Google Cloud Storage: immutable/content-addressed RAW payloads.
7. Secret Manager: database DSN, API token, optional webhook secrets and optional source credentials.

SQLite and filesystem RAW remain the local development/reference path.

## Required production settings

- `GEOWATCH_DB_URL=postgresql://...`
- `GEOWATCH_RAW_BUCKET=<bucket>`
- `GEOWATCH_API_TOKEN=<secret>`

Optional alert delivery:
- `GEOWATCH_WEBHOOK_URL=<secret>`
- `GEOWATCH_WEBHOOK_TOKEN=<secret>`

Source credentials remain opt-in and must only be mounted when the corresponding source is enabled.

## Health and observability

- `/health` verifies process availability and identifies the selected storage backend.
- `/v2/operational` exposes JSON operational counters.
- `/metrics` exposes Prometheus text metrics.
- `/v2/alerts/pending` exposes pending alert payloads through the authenticated API.
- `collector_runs` preserves source-level success/error history and record counts.
- `source_checkpoints` preserves incremental progress.
- `episode_changes` is the durable change lineage.
- `alert_outbox` provides retryable and deduplicated delivery state.

## Product surfaces

- `/dashboard` serves a static shell; real data are fetched from protected API routes at runtime.
- `/v2/map` exposes resolved episode/infrastructure points.
- `/v2/episodes/{episode_id}` provides event, claim, evidence, entity and change timeline context.
- `/v2/consumers/agrolog/feed` is a read-only filtered consumer view. It does not grant AgroLog MT write access to this database.

## Initial SLO targets

These are engineering targets, not claims about a deployment that has not yet been observed:

- API availability target: 99.5% monthly during the pre-1.0 phase.
- GDELT/GDACS collection freshness target: successful collection within 2 hours.
- Collector failure detection target: surface source error within one scheduled run.
- RAW durability target: every successfully parsed production payload has a content-addressed GCS object reference.
- Alert dispatch target: a queued webhook alert is attempted within the next configured dispatcher run.
- Database backup target: automated daily backup plus point-in-time recovery where the managed database supports it.

## Backup and disaster recovery

Production database provisioning should enable automated backups and point-in-time recovery before the first sustained collection. RAW objects are content-addressed and should use bucket versioning/retention according to cost and source-term requirements. Recovery drills should validate: database restore, API read path, checkpoint integrity, alert outbox integrity and one collector replay.

## Security

- Keep the repository private until redistribution/source-rights review is complete.
- Never commit API tokens, passwords, webhook secrets or DSNs.
- API service should require Cloud Run IAM and/or `GEOWATCH_API_TOKEN` for protected data endpoints.
- Dashboard HTML contains no dataset; protected data remain API-authenticated.
- Collector service account should receive only secret access, RAW bucket access and database connectivity needed for its task.
- Scheduler should only receive permission to invoke the configured jobs.
- External webhook delivery must use HTTPS and a bearer/shared credential where the destination supports it.
- Do not expose full copyrighted news bodies in reports or feeds.

## Deployment gate

`scripts/deploy_gcp.sh` is a reproducible deployment helper. Production is only considered live after all of the following are verified in the target GCP project:

1. PostgreSQL/PostGIS connection succeeds and migrations apply.
2. GCS RAW object is written by a collector execution.
3. Manual collector Cloud Run job exits successfully.
4. `/health`, `/v2/feed`, `/v2/episodes`, `/v2/map` and `/metrics` return expected authenticated responses.
5. Scheduler triggers at least one successful collector job.
6. If webhook delivery is enabled, a manual dispatcher job delivers one test alert and the outbox marks it delivered.
7. Backup/PITR policy is enabled for the production database.
8. A restore drill confirms database + checkpoint + lineage recovery.

Until those checks occur, the repository is deployment-ready but not a verified 24/7 deployment.
