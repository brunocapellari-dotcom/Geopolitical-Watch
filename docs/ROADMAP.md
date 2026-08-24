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
- PostgreSQL/PostGIS production schema/store
- durable filesystem/GCS RAW abstraction
- API v2 operational surfaces
- Prometheus metrics
- Cloud Run deployment assets

Live GCP deployment remains an external execution gate.

## v0.7 — product and alert layer — complete

- dashboard/map and episode timelines
- deterministic alert policies
- deduplicated outbox/retry delivery
- consumer-specific feeds
- AgroLog MT read-only profile
- webhook dispatcher
- product regression suite

## v0.8 — geopolitical knowledge and validation — complete

- advanced geopolitics curriculum
- structured geopolitical knowledge graph seed
- canonical legal/data/academic source registry
- strict `context_not_evidence` boundary
- strategic context attached to episode reports/API
- multi-theory context retrieval
- regional context retrieval
- historical analogy prompts with mandatory analogy limits
- source coverage inventory endpoint
- analyst review queue generation
- episode-quality flags
- alert precision/recall/FPR calibration framework
- auditable episode merge lineage
- safe split planning with forced recomputation
- v0.8 regression suite
- GitHub Actions release gate passed in PR #6

## v0.9 — validation, historical learning and strategic graph — next

- production deployment and restore drill when GCP credentials/infrastructure are available
- real multi-source historical coverage inventory/backfill
- labeled real-world episode corpus at scale
- persisted analyst review decisions
- apply/revert merge/split workflow with durable review state
- historical forecast/outcome calibration
- country strategic profiles
- rivalry/alliance graph
- larger strategic infrastructure graph
- sanctions and export-control context layer
- official maritime notice layer
- geoeconomic dependency metrics
- escalation indicator library
- competing-hypotheses analysis objects
- knowledge proposals generated from resolved analyst reviews

## v1.0 gate

v1.0 requires demonstrated production reliability, restore capability, empirically validated alert/convergence quality, stable API contracts, security/cost review, source-rights review and documented knowledge governance.

## Later

AIS/ADS-B, prediction markets and additional sensor/context layers enter only after terms, cost, privacy, stability and false-positive risks are reviewed.
