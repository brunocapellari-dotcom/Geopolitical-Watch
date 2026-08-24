# Geopolitical Watch

Standalone public-source geopolitical conflict monitoring and intelligence feed.

## Status

Version 0.3.0 is repository-ready and independent from AgroLog MT. AgroLog MT is only a downstream consumer of the versioned feed contract.

## What it does

- Collects high-frequency conflict-related news from GDELT DOC 2.0.
- Supports UCDP GED as a research-coded event layer when a token is configured.
- Supports ReliefWeb V2 as a curated humanitarian/institutional report layer when an approved appname is configured.
- Supports NASA FIRMS as a contextual thermal-anomaly sensor layer when a MAP_KEY is configured.
- Normalizes all sources into a common event contract.
- Clusters likely duplicate/related events.
- Separates OSINT signals, curated reports, research-coded events and sensor signals.
- Scores analyst priority without presenting the score as probability.
- Generates JSON and Markdown situational reports with related news links.
- Persists events, clusters and reports in SQLite for a zero-cost local start.
- Exposes `/v1/feed` and `/v1/reports/latest` over HTTP.

## Evidence discipline

A news article proves that a publication was observed, not automatically that the reported event occurred exactly as described. A thermal anomaly is contextual evidence and is never treated as proof of an attack by itself. The system preserves the evidence type and corroboration status in the output.

## Quick start

Python 3.12+ is sufficient; the core runtime uses the standard library only.

1. Run tests:
   `python -m unittest discover -s tests -v`
2. Collect enabled sources:
   `python -m geowatch collect`
3. Serve the latest feed/report:
   `python -m geowatch serve`
4. Read:
   - `GET /health`
   - `GET /v1/feed`
   - `GET /v1/reports/latest`

GDELT is enabled by default. UCDP, ReliefWeb and FIRMS are disabled until credentials are configured and their source terms are reviewed.

## Environment variables

- `UCDP_API_TOKEN` — UCDP API token.
- `RELIEFWEB_APPNAME` — pre-approved ReliefWeb appname.
- `FIRMS_MAP_KEY` — NASA FIRMS free MAP_KEY.
- `GEOWATCH_DB` — SQLite path used by the API server.
- `GEOWATCH_API_TOKEN` — optional bearer token for feed/report endpoints.
- `HOST`, `PORT` — API bind settings.

## Architecture

`sources -> raw snapshots -> normalized events -> clustering/corroboration -> priority -> reports -> versioned feed -> downstream consumers`

The standalone project owns its own storage, credentials, schedules, source policies, methods and reports. Downstream consumers must not write into the Geopolitical Watch database.

## Next development targets

1. Add source-specific incremental checkpoints and historical backfill orchestration.
2. Add geographic entity resolution and spatial clustering.
3. Add GDACS and selected official government/UN feeds.
4. Add AIS/ADS-B only as public/authorized contextual layers with strict terms review.
5. Add BigQuery adapter after the standalone local data contract stabilizes.
6. Add web dashboard/map after feed/API semantics are stable.
7. Add evaluation corpus for false positives, duplicate clustering and source corroboration.
