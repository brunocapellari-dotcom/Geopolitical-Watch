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

## v0.6 — operational data layer — implemented

- GDACS institutional context adapter
- ACLED OAuth adapter with cursor pagination
- PostgreSQL/PostGIS production schema and store
- SQLite/PostgreSQL backend factory
- durable RAW abstraction with filesystem/GCS backends
- API v2 episode/event/change query surfaces
- operational JSON and Prometheus metrics
- production image extras
- Cloud Run API/job + Cloud Scheduler + GCS deployment script

Live GCP deployment remains an external execution gate: repository assets do not prove that a Cloud Run service, database or scheduler is running.

## v0.7 — product and alert layer — next

- dashboard/map
- episode timelines
- alert policies and outbox delivery
- saved/consumer filters
- webhook delivery
- consumer-specific feeds
- AgroLog read-only consumer profile

## Later

AIS/ADS-B, sanctions, maritime notices, prediction markets and additional sensor/context layers enter only after terms, cost, stability, privacy and false-positive risks are reviewed.
