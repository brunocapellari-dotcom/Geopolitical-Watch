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

- GDACS context adapter
- ACLED OAuth/cursor adapter
- PostgreSQL/PostGIS production store
- filesystem/GCS RAW abstraction
- API v2 operational surfaces
- Prometheus metrics
- Cloud Run deployment assets

Live GCP deployment remains an external execution gate.

## v0.7 — product and alert layer — complete

- dashboard/map and timelines
- deterministic alert policies
- outbox/retry delivery
- consumer-specific feeds
- AgroLog MT read-only profile
- webhook dispatcher

## v0.8 — geopolitical knowledge and validation — complete

- advanced geopolitics curriculum
- structured theory/concept/case knowledge
- canonical source registry
- strict context/evidence boundary
- strategic context in reports/API
- review queue and quality flags
- source coverage inventory
- alert calibration framework
- merge lineage and split planning

## v0.9 — strategic intelligence and historical learning — implemented pending release gate

- persistent analyst review decisions
- governed knowledge proposals; no automatic knowledge mutation
- reversible merge/split/revert workflow with snapshots
- probabilistic forecast objects and resolutions
- Brier score and calibration tables
- competing hypotheses and discriminating indicators
- country strategic profile framework + initial seed
- temporal strategic relationship/chokepoint graph
- escalation/de-escalation indicator library
- geoeconomic supplier/route dependency metrics
- official sanctions source registry and normalized sanction model
- official maritime-warning source registry and normalized warning model
- read-only strategic API surfaces
- strategic CLI operations
- v0.9 regression suite

## v0.10 — empirical intelligence and production — next

- deploy API/collector/dispatcher to real GCP environment when credentials are available
- provision/validate Cloud SQL PostgreSQL/PostGIS, backups and PITR
- execute end-to-end smoke test and restore drill
- activate UCDP, ReliefWeb, FIRMS and ACLED only after required credentials/terms gates
- ingest official sanctions changes from UN/OFAC/UK sources
- ingest official NAVAREA/navigational-warning data where technically/legally available
- complete historical coverage inventory and bounded backfills
- build large labeled real-world conflict/episode corpus
- persist analyst review status/workflow beyond decision ledger
- expand country profiles toward global coverage
- expand alliances/rivalries/disputes/economic-dependency graph with dated sources
- expand strategic infrastructure graph: ports, canals, straits, pipelines, LNG, refineries, grids, cables, rail and critical nodes
- attach dated geoeconomic datasets to dependency metrics
- create formal forecast question templates and resolution criteria
- evaluate forecast/convergence/alert calibration on historical out-of-sample windows
- knowledge proposals -> review -> accepted/rejected versioned knowledge mutations
- load/chaos/backup/restore/cost/SLO tests
- source-rights and security audit before v1.0

## v1.0 gate

v1.0 requires demonstrated production reliability, restore capability, empirically validated convergence/alert/forecast quality, stable API contracts, security/cost/source-rights review and documented knowledge governance.

## Later

AIS/ADS-B, prediction markets, satellite-derived context and other sensor layers enter only after terms, cost, privacy, stability, operational-security and false-positive risks are reviewed.
