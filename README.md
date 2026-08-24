# Geopolitical Watch

Standalone public-source geopolitical conflict monitoring and intelligence feed.

## Status

Version **0.4.0** adds historical collection controls, source checkpoints, canonical geography, temporal/geospatial clustering and evaluation tooling. The project remains fully independent from AgroLog MT; AgroLog MT is only a downstream consumer of the versioned feed contract.

## What it does

- Collects high-frequency conflict-related news from GDELT DOC 2.0.
- Supports UCDP GED as a research-coded event layer when a token is configured.
- Supports ReliefWeb V2 as a curated humanitarian/institutional report layer when an approved appname is configured.
- Supports NASA FIRMS as a contextual thermal-anomaly sensor layer when a MAP_KEY is configured.
- Preserves raw snapshots with SHA-256 and collection metadata.
- Maintains per-source checkpoints and collector-run audit records.
- Supports bounded historical backfill for GDELT, UCDP and FIRMS.
- Normalizes country aliases and canonical event geography.
- Clusters related events across midnight and uses geographic distance when coordinates exist.
- Separates OSINT signals, curated reports, research-coded events and sensor signals.
- Adds descriptive source-quality metadata without subjective media-reputation scoring.
- Scores analyst priority without presenting the score as probability.
- Generates JSON and Markdown situational reports with related news links.
- Persists events, clusters, reports, checkpoints, raw-artifact metadata and run logs in SQLite.
- Exposes `/v1/feed` and `/v1/reports/latest` over HTTP.
- Includes replay/evaluation tooling for duplicate clustering and false positives.

## Evidence discipline

A news article proves that a publication was observed, not automatically that the reported event occurred exactly as described. A thermal anomaly is contextual evidence and is never treated as proof of an attack by itself. Source quality metadata describes provenance, governance and evidence role; it does not assign a simplistic reliability score to publishers.

## Quick start

Python 3.12+ is sufficient; the core runtime uses the standard library only.

1. Run tests: `python -m unittest discover -s tests -v`
2. Collect enabled sources: `python -m geowatch collect`
3. Backfill one supported source: `python -m geowatch backfill --source gdelt_conflict_news --start 2026-08-20T00:00:00Z --end 2026-08-21T00:00:00Z`
4. Evaluate clustering replay: `python -m geowatch evaluate --fixture tests/fixtures/clustering_eval.json`
5. Serve the latest feed/report: `python -m geowatch serve`
6. Read:
   - `GET /health`
   - `GET /v1/feed`
   - `GET /v1/reports/latest`

GDELT is enabled by default. UCDP, ReliefWeb and FIRMS remain disabled until credentials are configured and their source terms are reviewed.

## Historical behavior

- Incremental runs start from the latest successful checkpoint with a configurable overlap window to reduce boundary misses.
- GDELT backfill uses explicit `STARTDATETIME`/`ENDDATETIME` windows and remains bounded by the API result cap per query window; high-volume periods may require narrower windows or query partitioning.
- UCDP backfill uses `StartDate`/`EndDate` plus pagination; these filters follow UCDP endpoint semantics and must not be assumed to represent every possible event-date field.
- FIRMS backfill uses dated area requests in windows of at most five days; world-scale pulls can be large, so regional bounding boxes are preferred operationally.
- ReliefWeb historical automation is deliberately deferred in v0.4; the collector remains available for current/curated reports.

## Environment variables

- `UCDP_API_TOKEN` — UCDP API token.
- `RELIEFWEB_APPNAME` — pre-approved ReliefWeb appname.
- `FIRMS_MAP_KEY` — NASA FIRMS free MAP_KEY.
- `GEOWATCH_DB` — SQLite path used by the API server.
- `GEOWATCH_API_TOKEN` — optional bearer token for feed/report endpoints.
- `HOST`, `PORT` — API bind settings.

## Architecture

`sources -> raw snapshots -> checkpoints/run audit -> normalized events -> temporal/geospatial clustering -> corroboration/priority -> reports -> versioned feed -> downstream consumers`

The standalone project owns its own storage, credentials, schedules, source policies, methods and reports. Downstream consumers must not write into the Geopolitical Watch database.

## Current development direction

The next major step is **v0.5 — convergence engine**: correlate coded events, news, institutional reports and sensor signals into persistent conflict episodes, resolve infrastructure/routes, decompose confidence by evidence class and surface escalation/change detection for analyst review.
