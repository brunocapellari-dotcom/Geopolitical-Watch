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

## Release result

GitHub Actions run `32763294841` completed successfully for PR #4 on the final head SHA `43d54d5f7353904590572989d1f0d1f442336c33`.

PR #4 was merged into `main` with merge commit `63c58273085b89300b71ba577b2e4cdb1534081b`.

Cloud deployment is a separate operational gate and is not implied by this release.
