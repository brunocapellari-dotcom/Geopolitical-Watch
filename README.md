# Geopolitical Watch

Standalone public-source geopolitical conflict monitoring and intelligence feed.

## Status

Version **0.5.0** adds persistent conflict episodes, claims/evidence lineage, multilingual entity resolution, contradiction handling, decomposed evidence strength and a convergence engine. The project remains fully independent from AgroLog MT; AgroLog MT is only a downstream consumer of the versioned feed contract.

## What it does

- Collects high-frequency conflict-related news from GDELT DOC 2.0.
- Supports UCDP GED as a research-coded event layer when a token is configured.
- Supports ReliefWeb V2 as a curated humanitarian/institutional report layer when an approved appname is configured.
- Supports NASA FIRMS as a contextual thermal-anomaly sensor layer when a MAP_KEY is configured.
- Preserves raw snapshots with SHA-256 and collection metadata.
- Maintains per-source checkpoints and collector-run audit records.
- Supports bounded historical backfill for GDELT, UCDP and FIRMS.
- Normalizes country aliases and canonical event geography.
- Separates OSINT signals, curated reports, research-coded events and sensor signals.
- Builds persistent `ConflictEpisode` records above the immutable event layer.
- Preserves normalized claims, evidence relations, contradictions, corrections and retractions.
- Resolves multilingual strategic infrastructure/route aliases and actor entities.
- Decomposes evidence strength by provider independence, coded/institutional/sensor evidence, geolocation, entity resolution, recency and contradictions.
- Publishes `geowatch-feed-v2` episode intelligence while preserving `geowatch-feed-v1`.
- Persists events, entities, episodes, claims, evidence, lineage and change history in SQLite for local/reference execution.

## Evidence discipline

A news article proves that a publication was observed, not automatically that the reported event occurred exactly as described. A thermal anomaly is contextual evidence and is never treated as proof of an attack by itself. The `overall_index` in evidence strength is a triage index, not a probability that a claim is true.

## Quick start

Python 3.12+ is sufficient; the core runtime uses the standard library only.

1. Run tests: `python -m unittest discover -s tests -v`
2. Collect enabled sources: `python -m geowatch collect`
3. Backfill one supported source: `python -m geowatch backfill --source gdelt_conflict_news --start 2026-08-20T00:00:00Z --end 2026-08-21T00:00:00Z`
4. Evaluate clustering replay: `python -m geowatch evaluate --fixture tests/fixtures/clustering_eval.json`
5. Evaluate episode convergence: `python -m geowatch evaluate-episodes --fixture tests/fixtures/episode_eval.json`
6. Serve the API: `python -m geowatch serve`

## Architecture

`sources -> RAW/checkpoints -> events -> entity resolution -> claims/evidence -> persistent conflict episodes -> convergence/state/change detection -> reports -> versioned feeds -> consumers`

`Event` remains the immutable evidence record. `ConflictEpisode` is the persistent analytical unit.

## Compatibility

- `geowatch-feed-v1`: event/cluster feed retained for existing consumers.
- `geowatch-feed-v2`: episode-level feed with claims, evidence strength, entities and change flags.

## Current development direction

The next major step is **v0.6 — operational data layer**: add GDACS/ACLED adapters, PostgreSQL/PostGIS production storage, API v2 query surfaces, observability and deployment assets. v0.7 then adds dashboard, alert delivery and consumer profiles.
