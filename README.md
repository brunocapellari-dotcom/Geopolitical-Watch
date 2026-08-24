# Geopolitical Watch

Standalone public-source geopolitical conflict monitoring and strategic intelligence platform.

## Status

Version **0.10.0** adds the Empirical Intelligence & Production Readiness layer above v0.9: global country coverage registry, actor profiles, security-system context, critical-infrastructure graph, dated geoeconomic observation contracts, chokepoint exposure analysis, sanctions and maritime-warning normalization, formal multi-horizon forecast templates, leakage-safe historical backtesting, a historical crisis corpus, leading-indicator lead-time analysis, post-event learning and a hard-gated readiness model.

The project remains independent from AgroLog MT. AgroLog MT is a downstream read-only consumer of published feeds.

## Architecture

`sources -> durable RAW -> normalized events -> entities -> claims/evidence -> ConflictEpisodes -> geopolitical knowledge -> strategic graph/indicators -> review/hypotheses/forecasts -> outcomes/postmortems -> governed learning proposals -> API/dashboard/consumers`

Permanent rules:

- `Event` is preserved evidence.
- `ConflictEpisode` is the persistent analytical unit.
- knowledge context is not factual evidence;
- indicator scores are not probabilities;
- forecast probabilities do not change `EvidenceStrength`;
- analyst corrections preserve lineage and snapshots;
- learning proposals never auto-apply;
- historical backtests must enforce an information cutoff;
- 95% readiness requires all hard production/validation gates, not only a weighted score.

## v0.10 empirical intelligence

New durable components:

- `config/geopolitics/country_registry.json` — ISO-3166 global namespace coverage with enrichment status separated from profile quality;
- `config/geopolitics/actor_profiles.json` — sourced structural profiles for organizations/non-state actors;
- `config/geopolitics/security_systems.json` — collective-defence alliances, security organizations and partnerships modeled as different relationship types;
- `config/geopolitics/critical_infrastructure.json` — strategic chokepoints, ports, routes and infrastructure nodes;
- `config/geopolitics/geoeconomic_sources.json` — canonical official data sources for dated trade/energy/agriculture observations;
- `config/geopolitics/forecast_templates.json` — frozen questions and resolution criteria for 1/7/30/90-day forecast horizons;
- `config/geopolitics/historical_crises.json` — initial historical replay corpus with no-lookahead governance;
- `config/geopolitics/leading_indicators.json` — observable escalation/de-escalation indicator library;
- `config/readiness.json` — weighted readiness dimensions plus hard gates.

Core modules include `global_profiles`, `actor_profiles`, `security_systems`, `critical_infrastructure`, `geoeconomic_observations`, `chokepoints`, `sanctions_feed`, `maritime_feed`, `forecast_templates`, `historical_backtest`, `historical_corpus`, `leading_indicators`, `postmortem` and `readiness`.

## Forecasting and learning

Formal forecast questions preserve original probability, horizon, resolution rule and information cutoff. Historical evaluation rejects forecasts that were not strictly created before resolution or whose information cutoff is after forecast creation. Post-event reviews preserve the original evidence snapshot and can generate method-change proposals, always with `auto_apply=false`.

## Sanctions and maritime context

Sanctions ingestion normalizes issuing authority/list/reference/name/program/effective date. Official designations establish only what the issuing authority recorded; legal applicability still requires jurisdiction-specific review.

Navigational warnings remain separate from future AIS context. An official warning can establish navigation-safety context within its scope but does not establish conflict attribution or intent.

## Readiness

`GET /v2/readiness` exposes a conservative project-readiness assessment. A weighted score alone cannot produce 95% readiness. The hard gates are:

- live production smoke passed;
- database restore/PITR drill passed;
- source credentials and terms reviewed;
- historical out-of-sample validation completed;
- security and source-rights audit completed.

`scripts/preflight_v1.py` checks repository assets and required production environment variables without printing secret values.

## API

Compatibility remains for v1/v2 feeds, reports, episodes, events, changes, map, alerts, consumer feeds, review queue, coverage, operational metrics and dashboard.

Strategic/read-only surfaces include:

- `GET /v2/review-decisions`
- `GET /v2/episode-operations`
- `GET /v2/forecasts`
- `GET /v2/forecasts/summary`
- `GET /v2/geopolitics/countries`
- `GET /v2/geopolitics/actors`
- `GET /v2/geopolitics/security-systems`
- `GET /v2/geopolitics/infrastructure`
- `GET /v2/geopolitics/history`
- `GET /v2/geopolitics/graph`
- `GET /v2/readiness`

Strategic mutations remain CLI/internal operations rather than public HTTP write endpoints.

## Operational sources

- GDELT DOC 2.0 — enabled publication signal.
- GDACS — enabled institutional disaster/context signal.
- UCDP GED — supported, disabled until token/config review.
- ReliefWeb V2 — supported, disabled until approved appname.
- NASA FIRMS — supported, disabled until MAP_KEY and operational regions are configured.
- ACLED — supported with OAuth/cursor pagination, disabled until credentials and terms review.

## Deployment state

`scripts/deploy_gcp.sh` contains Cloud Run/API/collector/dispatcher/Scheduler/GCS assets, but repository presence does **not** mean a live cloud deployment exists. Production still requires a GCP project, PostgreSQL/PostGIS, secrets, source credentials where applicable and end-to-end smoke/restore validation.

## Release state

- v0.3 standalone baseline — complete.
- v0.4 history/quality — complete.
- v0.5 convergence engine — complete.
- v0.6 operational data layer — complete in code/CI; live deployment external.
- v0.7 product/alert layer — complete.
- v0.8 geopolitical knowledge + validation — complete.
- v0.9 strategic intelligence + historical learning — complete.
- v0.10 empirical intelligence + production readiness — **complete, CI passed and merged in PR #10**.
