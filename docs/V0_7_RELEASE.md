# v0.7.0 release gate

## Product layer delivered

- deterministic alert policies with required flags/state/strength filters
- version-aware alert deduplication
- persistent outbox and retryable webhook delivery
- dashboard shell with map and episode timeline data surfaces
- consumer-specific read-only feeds
- AgroLog MT read-only consumer profile
- CLI commands for alert dispatch and consumer feed export
- optional Cloud Run dispatcher job/scheduler in deployment helper

## Compatibility

- `geowatch-feed-v1` remains available.
- `geowatch-feed-v2` remains available.
- v2 episode/event/change APIs remain available.
- SQLite remains supported for local/test use.
- PostgreSQL/PostGIS remains the production backend.

## Release gate

This release is considered merged only after the full GitHub Actions test suite succeeds. Cloud deployment is a separate operational gate and is not implied by this release.
