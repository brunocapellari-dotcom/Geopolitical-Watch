# Geopolitical Watch

Standalone public-source geopolitical conflict monitoring and strategic intelligence platform.

## Status

Version **0.11.0** accelerates empirical validation and production readiness above v0.10. The project now has source-by-source activation gates, an executable historical backfill queue, bounded ReliefWeb historical collection, regional FIRMS operating areas, UCDP/ACLED reconciliation, official sanctions source normalization including the UK list, production smoke and non-destructive Cloud SQL restore-drill assets, Tier-1 country enrichment, expanded actor/infrastructure knowledge, a larger historical crisis corpus, rolling out-of-sample evaluation and a consolidated v1 release audit.

The project remains independent from AgroLog MT. AgroLog MT is a downstream read-only consumer of published feeds.

## Permanent evidence rules

- `Event` is preserved evidence; `ConflictEpisode` is the persistent analytical unit.
- Knowledge, profiles, graph edges, historical analogies and infrastructure criticality are context, not event verification.
- Sensor anomalies and navigational warnings never establish attack attribution by themselves.
- Provider disagreements are preserved instead of forcibly reconciled.
- Forecast probability never changes `EvidenceStrength`.
- Learning proposals never auto-apply.
- Historical validation enforces an information cutoff and reports yearly instability, not only aggregate scores.
- 95% readiness requires every hard production/validation gate in `config/readiness.json`.

## v0.11 acceleration

Operational governance:

- `config/operations/source_activation.json` — per-source credentials/terms gates; one blocked source does not block the global pipeline.
- `config/operations/backfill_plan.json` — bounded, checkpointed historical windows.
- `config/operations/firms_regions.json` — regional FIRMS areas; world queries are not the production default.
- `config/operations/official_context_sources.json` — current official sanctions/NAVAREA source registry.
- `config/audit/source_rights.json` — retention/redistribution/credential review matrix.
- `scripts/production_smoke.sh` — authenticated live API gate.
- `scripts/cloudsql_restore_drill.sh` — dry-run by default; isolated clone when explicitly applied.

Strategic/empirical acceleration:

- Tier-1 country profiles expanded to roughly 25 high-priority countries.
- actor profiles expanded across security/economic organizations and major armed actors;
- critical-infrastructure graph expanded beyond chokepoints into ports, terminals, pipelines and cable corridors;
- historical crisis corpus expanded from ~40 to ~78 cases while preserving no-lookahead behavior;
- `rolling_validation` reports forecast/alert/convergence performance per year and overall;
- `release_audit` requires production, recovery, empirical, cost, security and source-rights evidence.

## Readiness

`GET /v2/readiness` currently exposes a conservative weighted project-readiness estimate of approximately **0.77**. This is **not intelligence accuracy** and cannot become 0.95 while any hard gate remains false.

Hard gates:

- live production smoke passed;
- database restore/PITR drill passed;
- source credentials and terms reviewed;
- historical out-of-sample validation completed;
- security and source-rights audit completed.

## API additions in v0.11

- `GET /v2/source-activation`
- `GET /v2/backfill-plan`
- `GET /v2/geopolitics/profile-progress`
- `GET /v2/acceleration`

Existing v1/v2 feeds, reports, episodes, events, maps, alerts, consumers, review, forecasts, country/actor/security/infrastructure/history/graph and readiness endpoints remain compatible.

## Source state

Enabled without restricted credentials: GDELT publication signals, GDACS context, and official context registries that are public under their documented use conditions.

Supported but not marked production-active until their gates are satisfied: UCDP, ReliefWeb, NASA FIRMS and ACLED. Their adapters/backfill plans exist, but credentials/provider terms remain authoritative.

## Deployment state

Cloud Run, Cloud Scheduler, GCS and PostgreSQL/PostGIS deployment assets exist. Live GCP deployment, database restore evidence and restricted-source credential activation remain external execution gates and are **not** implied by repository CI.

## Release state

- v0.3 standalone baseline — complete.
- v0.4 history/quality — complete.
- v0.5 convergence engine — complete.
- v0.6 operational data layer — complete in code/CI; live deployment external.
- v0.7 product/alert layer — complete.
- v0.8 geopolitical knowledge + validation — complete.
- v0.9 strategic intelligence + historical learning — complete.
- v0.10 empirical intelligence + production readiness — complete.
- v0.11 accelerated production/empirical validation — implemented in this branch pending the release CI gate.
