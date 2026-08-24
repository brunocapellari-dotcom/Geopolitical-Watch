# Geopolitical Watch

Standalone public-source geopolitical conflict monitoring and strategic intelligence platform.

## Status

Version **0.9.0** adds the Strategic Intelligence & Historical Learning layer above v0.8: persistent analyst decisions, reversible episode corrections, country strategic profiles, a sourced temporal strategic graph, escalation indicators, competing hypotheses, probabilistic forecasts/calibration, geoeconomic dependency metrics, sanctions context and official maritime-warning context.

The project remains independent from AgroLog MT. AgroLog MT is a downstream read-only consumer of published feeds.

## Architecture

`sources -> durable RAW -> normalized events -> entities -> claims/evidence -> ConflictEpisodes -> geopolitical knowledge -> strategic graph/indicators -> review/hypotheses/forecasts -> outcomes/learning proposals -> API/dashboard/consumers`

Permanent rules:

- `Event` is preserved evidence.
- `ConflictEpisode` is the persistent analytical unit.
- knowledge context is not factual evidence;
- indicator scores are not probabilities;
- forecast probabilities do not change `EvidenceStrength`;
- analyst corrections preserve lineage and snapshots;
- learning proposals never auto-apply.

## Geopolitical knowledge

The advanced study program in `docs/GEOPOLITICS_CURRICULUM.md` covers international-relations theory, strategic studies, geoeconomics, political geography, international law, regional systems, information/OSINT uncertainty and historical cases.

v0.9 adds:

- `config/geopolitics/country_profiles.json` — structural country profiles;
- `config/geopolitics/strategic_graph.json` — sourced, time-bounded relationships and chokepoint exposure context;
- `config/geopolitics/escalation_indicators.json` — escalation/de-escalation observables;
- `config/geopolitics/sanctions_sources.json` — official sanctions source registry;
- `config/geopolitics/maritime_notice_sources.json` — official navigational-warning registry;
- `docs/STRATEGIC_INTELLIGENCE_MODEL.md` — learning/forecast/review governance.

Copyrighted academic/books material remains bibliographic reference + original synthesis only.

## Strategic learning loop

`review -> decision -> versioned operation/forecast -> observed outcome -> calibration -> knowledge proposal -> human/source review -> versioned knowledge change`

The strategic ledger stores:

- review decisions;
- merge/split/revert operations;
- forecasts and resolutions;
- knowledge proposals.

Repeated reviewed corrections may generate proposals, but `auto_apply=false` is permanent.

## Forecasting and competing hypotheses

Forecasts preserve original question, probability, timestamp, horizon and rationale. Resolutions are appended later. Historical calibration uses Brier score and probability bins.

Competing hypotheses store supporting, opposing and discriminating indicators. Their diagnostic score is not a posterior probability.

## Geoeconomic context

Initial quantitative tools include supplier HHI, effective supplier count, structural dependency index, route concentration and chokepoint exposure share. These are exposure measures, not loss forecasts.

## Sanctions and maritime context

Sanctions records preserve issuing authority, regime, target, measure, effective date and revocation. Legal applicability requires specialist review.

Navigational warnings are kept separate from future AIS context. An official warning can establish navigation-safety context within its scope but does not establish conflict attribution or intent.

## Operational sources

- GDELT DOC 2.0 — enabled publication signal.
- GDACS — enabled institutional disaster/context signal.
- UCDP GED — supported, disabled until token/config review.
- ReliefWeb V2 — supported, disabled until approved appname.
- NASA FIRMS — supported, disabled until MAP_KEY and operational regions are configured.
- ACLED — supported with OAuth/cursor pagination, disabled until credentials and terms review.

## Quick start

1. `python -m unittest discover -s tests -v`
2. `python -m geowatch collect`
3. `python -m geowatch serve`
4. `python -m geowatch metrics`
5. `python -m geowatch country-profile --country Japan`
6. `python -m geowatch forecast --subject-type episode --subject-id <id> --question "..." --probability 0.6 --horizon <ISO>`
7. `python -m geowatch forecast-summary`

Optional PostgreSQL/GCS dependencies: `pip install '.[production]'`.

## API

Compatibility remains:

- `GET /v1/feed`
- `GET /v1/reports/latest`
- `GET /v2/feed`
- `GET /v2/reports/latest`
- `GET /v2/episodes`
- `GET /v2/episodes/{episode_id}`
- `GET /v2/events`
- `GET /v2/changes`
- `GET /v2/map`
- `GET /v2/alerts/pending`
- `GET /v2/consumers/agrolog/feed`
- `GET /v2/review-queue`
- `GET /v2/coverage`
- `GET /v2/operational`
- `GET /metrics`
- `GET /health`
- `GET /dashboard`

v0.9 read-only strategic surfaces:

- `GET /v2/review-decisions`
- `GET /v2/episode-operations`
- `GET /v2/forecasts`
- `GET /v2/forecasts/summary`
- `GET /v2/geopolitics/countries`
- `GET /v2/geopolitics/graph`

Strategic mutations remain CLI/internal operations rather than public HTTP write endpoints.

## Deployment state

`scripts/deploy_gcp.sh` contains Cloud Run/API/collector/dispatcher/Scheduler/GCS assets, but repository presence does **not** mean a live cloud deployment exists. Production still requires a GCP project, PostgreSQL/PostGIS, secrets, source credentials where applicable and end-to-end smoke/restore validation.

## Release state

- v0.3 standalone baseline — complete.
- v0.4 history/quality — complete.
- v0.5 convergence engine — complete.
- v0.6 operational data layer — complete in code/CI; live deployment external.
- v0.7 product/alert layer — complete.
- v0.8 geopolitical knowledge + validation — complete.
- v0.9 strategic intelligence + historical learning — **complete, CI passed and merged in PR #8**.
