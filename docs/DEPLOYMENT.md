# Deployment model

## Zero-cost/local mode

- SQLite database
- local raw snapshots
- local JSON/Markdown reports
- standard-library HTTP API

This is the recommended first operational mode while source contracts and evaluation are stabilized.

## Cloud mode

A later deployment can run two separate workloads:

1. collector/report job on a schedule;
2. API service serving the latest stored report/feed.

Recommended separation:

- distinct service account for collection;
- read-only identity for API serving where practical;
- secrets only in a secret manager/environment injection;
- raw storage separate from application code;
- structured database separate from AgroLog MT.

## Schedule

The design supports hourly collection, but cadence must respect source quotas and source-specific update frequency. UCDP does not need to be polled at the same frequency as GDELT.

## Security

Set `GEOWATCH_API_TOKEN` before exposing the feed outside a trusted network. This v0.3 API is intentionally small and should sit behind a managed HTTPS service/reverse proxy in production.
