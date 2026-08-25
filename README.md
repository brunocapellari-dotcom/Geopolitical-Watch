# Geopolitical Watch

Standalone public-source geopolitical conflict monitoring and strategic intelligence platform.

## Status

Version **0.13.0** promotes the reliable public Beta into an operational-intelligence layer: persistent run history, explicit operational health, run-to-run deltas, source-backed historical validation assets, frozen multi-horizon forecasting benchmarks, expanded strategic profiles and chokepoint scenarios. Final production readiness remains a separate evidence gate.

The project remains independent from AgroLog MT. AgroLog MT is a downstream read-only consumer of published feeds.

## Permanent evidence rules

- `Event` is preserved evidence; `ConflictEpisode` is the persistent analytical unit.
- Knowledge, profiles, graph edges, historical analogies and infrastructure criticality are context, not event verification.
- GDACS disaster context and sensor signals cannot seed a conflict episode or raise EvidenceStrength by themselves.
- Provider disagreements are preserved rather than forcibly reconciled.
- EvidenceStrength is a heuristic index, never probability.
- Forecast probability never changes EvidenceStrength.
- Learning proposals never auto-apply.
- Research-coded history is not human gold or current evidence.
- Scenario packs are not forecasts.
- Missing economic observations are not zero-filled.
- 95% readiness requires every hard production/validation gate in `config/readiness.json`.

## Operational public Beta

The credential-free Beta currently uses GDELT as conflict-news signal and GDACS as context-only institutional disaster information.

`public sources -> RAW -> persistent SQLite Beta -> convergence -> ConflictEpisodes -> operational snapshot -> run delta -> digest -> versioned artifacts`

v0.13 adds:

- health classes `healthy`, `degraded`, `stale`, `partial`, `failed`;
- persistent bounded operational history;
- comparison with the previous run;
- source health/freshness changes;
- new episodes, state transitions and new change flags;
- EvidenceStrength shifts explicitly labelled non-probabilistic;
- concise operator digest with a “what changed” section.

GitHub Actions keeps Beta state in a versioned cache and retains database, RAW, state and report artifacts for audit. Live PR integration continues to exercise GDELT + GDACS.

## Empirical history and forecasting

Validated public upstreams have processed:

- UCDP Armed Conflict 26.1: 2,816 conflict-year rows;
- 628 reconstructed continuous UCDP episodes across 303 conflict IDs;
- 1,928 UCDP actors;
- 1,000 deterministic pre-gold identity labels;
- NGA World Port Index: 3,807 ports and 300 structural candidates;
- World Bank: 217 countries and 4,860 recent observations across five indicators;
- UN consolidated sanctions: 1,011 unique IDs in the validated snapshot;
- UK Sanctions List: 6,334 Unique IDs in the validated snapshot.

v0.13 additionally generates:

- 150 prioritized research-coded UCDP chronologies;
- an explicit queue of human-gold review candidates, never auto-labelled gold;
- at least 200 frozen historical forecast questions;
- horizons of 1, 7, 30 and 90 days;
- rolling temporal evaluation by year, region and source mix.

Historical forecasts are retrospective benchmarks, not a fabricated historical live track record.

## Strategic knowledge

The structured geopolitical knowledge layer includes competing theoretical lenses, country profiles, actor profiles, security systems, strategic infrastructure, sanctions, historical cases, geoeconomic context and escalation indicators.

v0.13 enriches Tier-2 countries to the >=80% coverage target and expands the reviewed structural actor library beyond 50 entries. Current activity still requires live sources.

Five core chokepoint scenario templates are maintained for:

- Strait of Hormuz;
- Bab el-Mandeb / Suez;
- Strait of Malacca;
- Panama Canal;
- Turkish Straits.

They require dated route-share inputs and uncertainty bands before quantitative use.

## Infrastructure and geoeconomics

WPI candidates now pass through a promotion-review framework. A port can become `review_ready` from structural signals, but **one source cannot establish reviewed geopolitical criticality** and cannot establish current operational disruption.

World Bank observations are attached as dated country context. The geoeconomic dependency utilities are designed for dated trade/energy/agriculture observations and preserve missing values instead of interpreting absence as zero.

## Readiness

`GET /v2/readiness` exposes a conservative weighted project-state estimate of approximately **0.86** for v0.13. This is **not intelligence accuracy**.

Hard gates still open:

- live GCP production smoke;
- database restore/PITR drill evidence;
- credentials/terms approval for all enabled restricted production sources;
- reviewed large historical out-of-sample validation / human-gold evidence;
- final security, cost and source-rights audit evidence.

The release-audit layer emits an explicit v1 go/no-go and cannot infer those gates from repository code or CI.

## Source state

Public layers validated without restricted API credentials include GDELT, GDACS, UCDP bulk datasets under their published terms, NGA World Port Index, World Bank API and official UN/UK sanctions sources.

Supported but not marked production-active until their gates are satisfied: tokenized UCDP API if needed, ReliefWeb, NASA FIRMS and ACLED.

## Deployment state

Cloud Run, Cloud Scheduler, GCS and PostgreSQL/PostGIS deployment assets exist. Live GCP deployment, database restore evidence and restricted-source activation remain external execution gates and are not implied by repository CI or the GitHub-hosted Beta.

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
- v0.12 reliable public Beta + empirical history — complete.
- v0.13 operational intelligence — release requires cumulative and live-upstream CI gates; external v1 hard gates remain separate.
