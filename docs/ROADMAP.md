# Roadmap

## v0.3 — standalone baseline — complete

- independent package
- GDELT, UCDP, ReliefWeb and FIRMS adapters
- normalized event model
- provider-aware corroboration
- priority scoring
- SQLite persistence
- reports with related news
- versioned feed API
- AgroLog consumer boundary

## v0.4 — historical and quality layer — complete

- source checkpoints and run audit
- RAW SHA-256 metadata
- bounded historical backfill
- canonical countries
- temporal/geospatial clustering
- source-quality metadata
- replay evaluation

## v0.5 — convergence engine — complete

- persistent `ConflictEpisode`
- Claim -> Evidence lineage
- multilingual entity resolution
- strategic infrastructure/route catalog
- decomposed evidence strength
- contradictions, corrections and restoration/supersession
- deterministic episode states
- change lineage
- `geowatch-feed-v2` with v1 compatibility
- convergence regression suite

## v0.6 — operational data layer — complete in code/CI

- GDACS institutional context adapter
- ACLED OAuth adapter with cursor pagination
- PostgreSQL/PostGIS production schema and store
- SQLite/PostgreSQL backend factory
- durable RAW abstraction with filesystem/GCS backends
- API v2 episode/event/change query surfaces
- operational JSON and Prometheus metrics
- production image extras
- Cloud Run API/job + Cloud Scheduler + GCS deployment assets

Live GCP deployment remains an external execution gate: repository assets do not prove that a Cloud Run service, database or scheduler is running.

## v0.7 — product and alert layer — complete in code pending release gate

- dashboard/map
- episode timelines
- deterministic alert policies
- alert outbox with delivery retry
- consumer filters
- webhook delivery
- consumer-specific feeds
- AgroLog MT read-only consumer profile
- API map/alerts/consumer endpoints
- CLI dispatcher and consumer feed commands
- regression tests for alert dedupe/filtering and product surfaces

## v0.8 — validation and operational hardening — next

- real GCP deployment and end-to-end smoke tests
- Cloud SQL/PostGIS backup/PITR validation
- historical multi-source backfill inventory
- larger real-world labeled episode corpus
- analyst review queue and episode merge/split lineage
- alert precision/recall/fatigue calibration
- load/chaos/restore/cost/SLO testing

## Later

Sanctions, maritime notices, AIS/ADS-B, additional official sensor/context feeds, prediction markets and other contextual layers enter only after terms, cost, stability, privacy and false-positive risks are reviewed.
