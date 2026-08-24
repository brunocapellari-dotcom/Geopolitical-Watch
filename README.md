# Geopolitical Watch

Standalone public-source geopolitical conflict monitoring and strategic intelligence platform.

## Status

Version **0.12.0** turns the repository into a substantially more reliable public Beta while deepening empirical history. The release validates real public upstreams in GitHub Actions, persists the Beta database between runs, distinguishes transient source degradation from structural failures, adds HTTP retry/backoff, builds a concise operator digest, and prevents disaster/sensor context from creating conflict episodes by itself.

The project remains independent from AgroLog MT. AgroLog MT is a downstream read-only consumer of published feeds.

## Permanent evidence rules

- `Event` is preserved evidence; `ConflictEpisode` is the persistent analytical unit.
- Knowledge, profiles, graph edges, historical analogies and infrastructure criticality are context, not event verification.
- GDACS disaster context and sensor signals such as FIRMS cannot seed `ConflictEpisode`, create conflict claims or raise evidence strength by themselves.
- Context-only events may enrich an existing episode only after a stronger match and do not refresh the episode's conflict state.
- Provider disagreements are preserved instead of forcibly reconciled.
- Forecast probability never changes `EvidenceStrength`.
- Learning proposals never auto-apply.
- Historical validation enforces an information cutoff and reports temporal instability, not only aggregate scores.
- 95% readiness requires every hard production/validation gate in `config/readiness.json`.

## v0.12 public Beta

The credential-free Beta profile currently enables:

- GDELT as the public conflict-news signal;
- GDACS as context-only institutional disaster information.

The Beta workflow:

`public sources -> raw snapshots -> persistent SQLite Beta store -> convergence -> ConflictEpisodes -> coverage/health -> concise operator digest -> versioned artifacts`

Operational safeguards include:

- hourly GitHub Actions execution with concurrency control;
- persistent Beta SQLite state restored/saved through a versioned cache;
- fail-closed shell pipelines (`pipefail`);
- explicit health output distinguishing transient 429/5xx/timeout degradation from parser/schema/configuration failures;
- GDELT HTTP retry/backoff;
- conflict-coverage flag separate from generic pipeline health;
- RAW/report/database artifacts retained for audit;
- live PR smoke against GDELT + GDACS;
- a concise digest with source health, freshness, top episodes, change flags and evidence-strength labels explicitly marked as non-probabilistic.

If GDELT is rate-limited while GDACS remains available, the Beta may continue as **degraded**, but it reports conflict coverage as unavailable and does not manufacture conflict episodes from disaster context.

## Empirical history and public-data validation

Current live-upstream integration has successfully processed, as sanity-check quantities rather than completeness guarantees:

- UCDP Armed Conflict 26.1: **2,816** conflict-year rows;
- **628** reconstructed continuous UCDP episodes across **303** conflict IDs;
- UCDP Actor 26.1: **1,928** parsed actors;
- **1,000** deterministic pre-gold identity labels (not human gold);
- NGA World Port Index: **3,807** ports with **300** structural enrichment candidates;
- World Bank: **217** countries and **4,860** recent geoeconomic observations across five indicators;
- UN consolidated sanctions: **1,011** unique IDs in the validated snapshot;
- UK Sanctions List: **6,334** Unique IDs in the validated snapshot, kept separate from flattened name-row counts.

The empirical-history layer keeps project-curated cases and UCDP research-coded episodes distinct. UCDP history is neither live-event confirmation nor human-gold review data.

The retrospective UCDP base-rate benchmark now scores only outcome classes that are actually represented by the termination dataset. Unsupported classes are not silently treated as negatives.

## v0.11 acceleration retained

Operational governance remains available:

- `config/operations/source_activation.json` — per-source credentials/terms gates; one blocked source does not block the global pipeline.
- `config/operations/backfill_plan.json` — bounded, checkpointed historical windows.
- `config/operations/firms_regions.json` — regional FIRMS areas; world queries are not the production default.
- `config/operations/official_context_sources.json` — official sanctions/NAVAREA source registry.
- `config/audit/source_rights.json` — retention/redistribution/credential review matrix.
- `scripts/production_smoke.sh` — authenticated live API gate.
- `scripts/cloudsql_restore_drill.sh` — dry-run by default; isolated clone when explicitly applied.

## Readiness

`GET /v2/readiness` exposes a conservative weighted project-readiness estimate of approximately **0.82** for v0.12. This is **not intelligence accuracy** and cannot become 0.95 while any hard gate remains false.

Hard gates still open:

- live production smoke passed;
- database restore/PITR drill passed;
- restricted-source credentials and terms reviewed;
- large historical out-of-sample validation completed;
- security and source-rights audit completed.

The GitHub-hosted public Beta and public-upstream CI materially improve operational readiness, but they are not substitutes for a real production deployment or disaster-recovery evidence.

## API

The v1/v2 feeds, reports, episodes, events, maps, alerts, consumers, review, forecasts, country/actor/security/infrastructure/history/graph, source activation, backfill and readiness endpoints remain compatible. `/health` reports the package version from a single canonical version constant.

## Source state

Enabled without restricted credentials: GDELT publication signals, GDACS context and public official/context registries under their documented use conditions.

Public bulk/reference layers validated without restricted API credentials include UCDP bulk datasets under their published CC BY 4.0 terms, NGA World Port Index, World Bank API and official UN/UK sanctions sources.

Supported but not marked production-active until their gates are satisfied: tokenized UCDP API, ReliefWeb, NASA FIRMS and ACLED. Their adapters/backfill plans exist, but credentials/provider terms remain authoritative.

## Deployment state

Cloud Run, Cloud Scheduler, GCS and PostgreSQL/PostGIS deployment assets exist. Live GCP deployment, database restore evidence and restricted-source activation remain external execution gates and are **not** implied by repository CI or the GitHub-hosted public Beta.

## Release state

- v0.3 standalone baseline — complete.
- v0.4 history/quality — complete.
- v0.5 convergence engine — complete.
- v0.6 operational data layer — complete in code/CI; live deployment external.
- v0.7 product/alert layer — complete.
- v0.8 geopolitical knowledge + validation — complete.
- v0.9 strategic intelligence + historical learning — complete.
- v0.10 empirical intelligence + production readiness — complete.
- v0.11 accelerated production/empirical validation — complete.
- v0.12 reliable public Beta + empirical history — **release candidate in PR #20; final cumulative/live gates required before merge**.
