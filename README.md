# Geopolitical Watch

Standalone public-source geopolitical conflict monitoring and intelligence feed.

## Status

Version **0.6.0** adds the operational data layer above the v0.5 convergence engine: GDACS context, ACLED OAuth/cursor support, PostgreSQL/PostGIS production storage, durable GCS RAW evidence, API v2 queries, Prometheus metrics and reproducible GCP deployment assets. The project remains fully independent from AgroLog MT; AgroLog MT is only a downstream consumer of published feeds.

## Architecture

`sources -> durable RAW/checkpoints -> normalized events -> entity resolution -> claims/evidence -> persistent conflict episodes -> convergence/state/change detection -> PostgreSQL/PostGIS -> API/feed v1+v2 -> consumers`

- `Event` remains the preserved evidence record.
- `ConflictEpisode` is the persistent analytical unit.
- SQLite remains the zero-cost local/test backend.
- PostgreSQL/PostGIS is the production backend when `GEOWATCH_DB_URL` is set.
- Filesystem RAW remains available locally; GCS is selected with `GEOWATCH_RAW_BUCKET` or a `gs://` RAW location.

## Sources

- GDELT DOC 2.0 — enabled high-frequency publication signal.
- GDACS — enabled institutional disaster/context signal; never conflict attribution by itself.
- UCDP GED — supported, disabled until token/config review.
- ReliefWeb V2 — supported, disabled until approved appname.
- NASA FIRMS — supported, disabled until MAP_KEY/operational region is configured.
- ACLED — supported with OAuth and cursor pagination, disabled until myACLED credentials and terms review.

## Evidence discipline

A publication proves publication observation, not automatic confirmation of the reported event. A thermal anomaly or disaster alert is contextual evidence, not attack attribution. `EvidenceStrength.overall_index` is a triage/evidence-strength index, not a probability that a claim is true.

## Quick start

1. `python -m unittest discover -s tests -v`
2. `python -m geowatch collect`
3. `python -m geowatch serve`
4. `python -m geowatch metrics`

Optional PostgreSQL/GCS dependencies: `pip install '.[production]'`.

## API

Compatibility endpoints remain:
- `GET /v1/feed`
- `GET /v1/reports/latest`

Operational episode API:
- `GET /v2/feed`
- `GET /v2/reports/latest`
- `GET /v2/episodes?country=&state=&since=&min_strength=&limit=`
- `GET /v2/episodes/{episode_id}`
- `GET /v2/events?country=&since=&limit=`
- `GET /v2/changes?since=&limit=`
- `GET /v2/operational`
- `GET /metrics`
- `GET /health`

Set `GEOWATCH_API_TOKEN` before exposing the service outside a trusted boundary.

## Production variables

- `GEOWATCH_DB_URL` — PostgreSQL/PostGIS DSN.
- `GEOWATCH_RAW_BUCKET` — GCS bucket for immutable RAW artifacts.
- `GEOWATCH_RAW_PREFIX` — optional object prefix, default `raw`.
- `GEOWATCH_API_TOKEN` — API bearer token.
- source credentials such as `UCDP_API_TOKEN`, `RELIEFWEB_APPNAME`, `FIRMS_MAP_KEY`, and ACLED credentials are only required when those sources are enabled.

## Deployment state

`scripts/deploy_gcp.sh` provisions/deploys Cloud Run API + Cloud Run collector job + Cloud Scheduler + GCS wiring, but repository presence does **not** mean the cloud service has been deployed. A live deployment requires a GCP project, PostgreSQL/PostGIS DSN secret and API token secret, followed by a collector/API smoke test.

## Next

v0.7 adds the product layer: authenticated dashboard/map, alert policies/outbox delivery, timelines and consumer-specific feeds while keeping Geopolitical Watch independent from downstream systems.
