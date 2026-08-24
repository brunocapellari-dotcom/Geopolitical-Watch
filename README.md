# Geopolitical Watch

Standalone public-source geopolitical conflict monitoring and intelligence platform.

## Status

Version **0.7.0** adds the product and alert layer above the v0.6 operational data stack: deterministic alert policies, deduplicated outbox delivery, consumer-specific feeds, an AgroLog MT read-only profile, dashboard/map and episode timelines. The project remains fully independent from AgroLog MT; AgroLog MT is only a downstream consumer of published feeds.

## Architecture

`sources -> durable RAW/checkpoints -> normalized events -> entity resolution -> claims/evidence -> persistent conflict episodes -> convergence/state/change detection -> PostgreSQL/PostGIS -> alerts/dashboard/API -> consumers`

- `Event` remains the preserved evidence record.
- `ConflictEpisode` is the persistent analytical unit.
- SQLite remains the local/test backend.
- PostgreSQL/PostGIS is the production backend when `GEOWATCH_DB_URL` is set.
- Filesystem RAW remains available locally; GCS is selected with `GEOWATCH_RAW_BUCKET` or a `gs://` RAW location.
- Alert delivery uses an outbox so failures do not destroy or overwrite the underlying episode/evidence history.

## Sources

- GDELT DOC 2.0 — enabled high-frequency publication signal.
- GDACS — enabled institutional disaster/context signal; never conflict attribution by itself.
- UCDP GED — supported, disabled until token/config review.
- ReliefWeb V2 — supported, disabled until approved appname.
- NASA FIRMS — supported, disabled until MAP_KEY and operational regions are configured.
- ACLED — supported with OAuth and cursor pagination, disabled until myACLED credentials and terms review.

## Evidence discipline

A publication proves publication observation, not automatic confirmation of the reported event. A thermal anomaly or disaster alert is contextual evidence, not attack attribution. `EvidenceStrength.overall_index` is a triage/evidence-strength index, not a probability that a claim is true. Contradictions, corrections and retractions remain in lineage.

## Quick start

1. `python -m unittest discover -s tests -v`
2. `python -m geowatch collect`
3. `python -m geowatch serve`
4. `python -m geowatch metrics`
5. `python -m geowatch consumer-feed --consumer agrolog`
6. `python -m geowatch dispatch-alerts`

Optional PostgreSQL/GCS dependencies: `pip install '.[production]'`.

## API and dashboard

Compatibility endpoints remain:
- `GET /v1/feed`
- `GET /v1/reports/latest`

Episode/product API:
- `GET /v2/feed`
- `GET /v2/reports/latest`
- `GET /v2/episodes?country=&state=&since=&min_strength=&limit=`
- `GET /v2/episodes/{episode_id}`
- `GET /v2/events?country=&since=&limit=`
- `GET /v2/changes?since=&limit=`
- `GET /v2/map?limit=`
- `GET /v2/alerts/pending?limit=`
- `GET /v2/consumers/agrolog/feed`
- `GET /v2/operational`
- `GET /metrics`
- `GET /health`
- `GET /dashboard` — static authenticated-data shell with map/timeline client.

Set `GEOWATCH_API_TOKEN` before exposing data endpoints outside a trusted boundary. The dashboard HTML itself contains no conflict dataset; it requests protected API data at runtime.

## Alerts

Policies live in `config/alerts.json`. Current baseline policies cover escalating episodes, strategic infrastructure state changes, contradiction/retraction review and ceasefire/de-escalation changes.

Alerts are deterministic, version-aware and deduplicated into `alert_outbox`. Delivery is a separate step:

`python -m geowatch dispatch-alerts`

Environment:
- `GEOWATCH_WEBHOOK_URL` — destination webhook.
- `GEOWATCH_WEBHOOK_TOKEN` — optional bearer token.

A failed delivery returns the alert to pending state and preserves attempts/errors for later retry.

## Consumer feeds

Consumer policies are read-only filters over Geopolitical Watch data. `config/consumers/agrolog.json` filters for areas relevant to agriculture/logistics such as energy, fertilizers, shipping, trade, FX, agriculture, logistics and infrastructure. It does not allow AgroLog MT to write to the Geopolitical Watch database.

## Production variables

- `GEOWATCH_DB_URL` — PostgreSQL/PostGIS DSN.
- `GEOWATCH_RAW_BUCKET` — GCS bucket for immutable RAW artifacts.
- `GEOWATCH_RAW_PREFIX` — optional object prefix, default `raw`.
- `GEOWATCH_API_TOKEN` — API bearer token.
- `GEOWATCH_WEBHOOK_URL` — optional alert webhook.
- `GEOWATCH_WEBHOOK_TOKEN` — optional webhook bearer token.
- source credentials such as `UCDP_API_TOKEN`, `RELIEFWEB_APPNAME`, `FIRMS_MAP_KEY` and ACLED credentials are required only when those sources are enabled.

## Deployment state

`scripts/deploy_gcp.sh` provisions/deploys the Cloud Run API, collector job, alert-dispatch job, Cloud Scheduler and GCS wiring. Repository presence does **not** mean the cloud service has been deployed. A live deployment still requires a GCP project, PostgreSQL/PostGIS DSN secret, API token secret and, if webhooks are used, webhook secrets, followed by collector/API/dispatcher smoke tests.

## Release state

- v0.3 standalone baseline — complete.
- v0.4 history/quality — complete.
- v0.5 convergence engine — complete.
- v0.6 operational data layer — complete in code and CI; live cloud deployment remains external.
- v0.7 product/alert layer — complete in code pending this release gate/CI merge.
