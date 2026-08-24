# Roadmap

## v0.3 — standalone baseline — complete

- independent package
- GDELT news ingestion
- UCDP pagination-ready authenticated ingestion
- ReliefWeb authenticated appname ingestion
- FIRMS contextual sensor ingestion
- normalized event model
- provider-aware corroboration
- priority scoring
- SQLite persistence
- reports with related news
- versioned feed API
- AgroLog consumer boundary

## v0.4 — historical and quality layer — implemented

- source checkpoint tables
- collector-run and raw-artifact audit metadata
- configurable incremental lookback with overlap
- bounded historical backfill for GDELT, UCDP and FIRMS
- canonical country aliases
- cross-midnight temporal clustering
- geospatial distance guardrails
- descriptive publisher/source quality metadata
- reports built from recent persisted history, not only the current fetch
- replay tests from stored fixtures
- false-positive and duplicate pairwise evaluation

Known limits retained intentionally in v0.4:

- ReliefWeb historical backfill is not automated.
- GDELT backfill can hit the per-window result cap in dense periods and may require narrower/partitioned queries.
- FIRMS world-scale historical pulls should be replaced by bounded regional requests when operational regions are defined.

## v0.5 — convergence engine

- correlate coded events, news, institutional reports and sensors
- persistent conflict episode IDs
- infrastructure/route entity resolution
- confidence decomposition by evidence class
- escalation/change detection
- analyst review queue
- source/event lineage graph
- improved multilingual entity matching

## v0.6 — operational intelligence

- authenticated dashboard/map
- saved filters and regions
- event timelines
- alert policies
- webhook/feed consumers
- downstream impact adapters

## Later

AIS/ADS-B, sanctions, prediction markets and other contextual layers only after terms, cost, stability, privacy and false-positive risks are reviewed.
