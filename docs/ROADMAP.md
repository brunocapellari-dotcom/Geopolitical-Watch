# Roadmap

## v0.3 — standalone baseline — complete

Independent package, source adapters, normalized events, corroboration, scoring, SQLite, reports and versioned feed API.

## v0.4 — historical and quality layer — complete

Checkpoints, RAW audit, bounded backfill, canonical geography, temporal/geospatial clustering, quality metadata and replay evaluation.

## v0.5 — convergence engine — complete

Persistent `ConflictEpisode`, Claim -> Evidence lineage, multilingual entity resolution, strategic infrastructure catalog, decomposed evidence strength, contradictions/corrections, deterministic states and feed v2.

## v0.6 — operational data layer — complete in code/CI

GDACS/ACLED adapters, PostgreSQL/PostGIS, durable RAW abstraction, API v2, metrics and Cloud Run deployment assets. Live GCP deployment remains external.

## v0.7 — product and alert layer — complete

Dashboard/map, timelines, deterministic alert policies, outbox/retry delivery, consumer feeds and AgroLog MT read-only profile.

## v0.8 — geopolitical knowledge and validation — complete

Advanced geopolitics curriculum, theory/concept/case knowledge, canonical source registry, strict context/evidence boundary, review queue, coverage inventory and validation framework.

## v0.9 — strategic intelligence and historical learning — complete

Persistent review decisions, reversible episode operations, probabilistic forecasts, calibration, competing hypotheses, country profiles, strategic graph, escalation indicators, geoeconomic context, sanctions/maritime models and governed learning proposals.

## v0.10 — empirical intelligence and production readiness — complete

- global ISO country/territory registry with enrichment status separated from coverage;
- structural actor-profile registry;
- security-system model distinguishing formal alliance, collective-security organization, partnership and dialogue;
- expanded critical-infrastructure/chokepoint graph;
- canonical geoeconomic-source registry and dated observation contract;
- global chokepoint exposure engine with alternatives and unmitigated share;
- UN/OFAC sanctions feed normalization and change detection;
- official maritime-warning normalization, distinct from AIS and conflict attribution;
- formal forecast templates with frozen resolution rules;
- multi-horizon forecasting for 1/7/30/90-day use cases;
- temporal backtest evaluator with no-lookahead checks;
- initial historical crisis corpus with information-cutoff behavior;
- leading-indicator library and lead-time statistics;
- post-event/postmortem learning loop with non-automatic proposals;
- weighted readiness model plus mandatory hard gates;
- v1 production preflight that never prints secrets;
- v0.10 regression and API smoke coverage;
- GitHub Actions release gate passed in PR #10.

Current conservative weighted project-readiness baseline after this code wave is approximately **0.71**. This is project readiness, not analytical accuracy. The target cannot reach 0.95 until all hard gates pass.

## v0.11 — production and empirical validation — next

1. deploy API/collector/dispatcher to a real GCP environment;
2. provision Cloud SQL PostgreSQL/PostGIS and validate backup/PITR restore;
3. activate UCDP with real token and execute bounded historical backfill;
4. activate ReliefWeb after approved appname and coverage audit;
5. activate FIRMS with regional queries and false-attribution safeguards;
6. activate ACLED after credentials/terms review and reconcile with UCDP;
7. operationalize official UN/OFAC/UK sanctions change ingestion;
8. operationalize NAVAREA/navigational-warning ingestion where technically and legally available;
9. enrich global country profiles from baseline to sourced strategic profiles;
10. expand actor profiles to international organizations, armed groups and strategic state-linked entities;
11. expand sourced alliances/rivalries/disputes/dependency graph with validity intervals;
12. expand critical-infrastructure graph to global ports, pipelines, LNG, refineries, grids, cables, rail and strategic nodes;
13. expand historical crisis corpus from seed to a large source-backed evaluation set;
14. execute rolling out-of-sample convergence/alert/forecast calibration and postmortems;
15. complete security, cost, source-rights and recovery audit and prepare v1.0 release candidate.

## v1.0 gate

v1.0 requires demonstrated production reliability, restore capability, empirically validated convergence/alert/forecast quality, stable API contracts, security/cost/source-rights review and documented knowledge governance.

## Later

AIS/ADS-B, prediction markets, satellite-derived context and other sensor layers enter only after terms, cost, privacy, stability, operational-security and false-positive risks are reviewed.
