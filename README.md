# Geopolitical Watch

Standalone public-source geopolitical conflict monitoring and intelligence platform.

## Status

Version **0.8.0** adds a permanent geopolitical knowledge and validation layer above the v0.7 product stack. Conflict episodes can now retrieve structured strategic context from international-relations theory, geoeconomics, strategic geography, regional systems and historical cases while preserving a hard boundary between **knowledge context** and **factual evidence**.

## Architecture

`sources -> durable RAW/checkpoints -> normalized events -> entity resolution -> claims/evidence -> persistent conflict episodes -> convergence/state/change detection -> geopolitical knowledge context -> validation/review -> alerts/dashboard/API -> consumers`

- `Event` remains the preserved evidence record.
- `ConflictEpisode` remains the persistent analytical unit.
- `strategic_context` is analytical knowledge and always carries `context_not_evidence=true`.
- Knowledge context cannot increase evidence strength or verify an event/claim.
- SQLite remains the local/test backend; PostgreSQL/PostGIS remains the production backend.

## Geopolitical learning layer

The permanent study program is documented in `docs/GEOPOLITICS_CURRICULUM.md` and covers:

- realism, structural realism, liberal approaches, constructivism, English School and critical geopolitics;
- deterrence, coercion, escalation, alliances, security dilemma and power transition;
- sea power, land power, strategic depth, chokepoints and infrastructure geopolitics;
- sanctions, geoeconomic fragmentation, energy, trade, finance, technology and economic statecraft;
- international law, UN Charter and international humanitarian law;
- domestic politics, state capacity, nationalism and civil-military relations;
- information operations, OSINT uncertainty, competing hypotheses and forecast calibration;
- Europe/Eurasia, Middle East, Indo-Pacific, Africa, Latin America, Arctic and global commons;
- structured historical case studies with explicit analogy limits.

Structured knowledge lives in `config/geopolitics/knowledge.json`; canonical-source metadata lives in `config/geopolitics/sources.json`. Copyrighted books/research are bibliographic references and original summaries only, not mirrored text.

## Validation and learning loop

v0.8 adds:

- `/v2/coverage` — observed collector coverage inventory;
- `/v2/review-queue` — deterministic analyst-review candidates for uncertain/contradictory episodes;
- geopolitical context in `/v2/episodes/{episode_id}` and episode reports;
- alert precision/recall/false-positive calibration utilities;
- quality flags for low evidence, single-provider dependence, unresolved geography, contradiction/retraction and emerging episodes;
- auditable episode merge operations and safe split plans that preserve lineage and force recomputation instead of silently rewriting history.

## Sources

Operational source adapters remain:

- GDELT DOC 2.0 — enabled high-frequency publication signal.
- GDACS — enabled institutional disaster/context signal; never conflict attribution by itself.
- UCDP GED — supported, disabled until token/config review.
- ReliefWeb V2 — supported, disabled until approved appname.
- NASA FIRMS — supported, disabled until MAP_KEY and operational regions are configured.
- ACLED — supported with OAuth/cursor pagination, disabled until credentials and terms review.

The geopolitical knowledge source registry additionally includes primary legal texts, official datasets/analysis and canonical academic references.

## Evidence discipline

A publication proves publication observation, not automatic confirmation of the reported event. A sensor or disaster alert is contextual evidence, not attack attribution. `EvidenceStrength.overall_index` is an evidence-strength/triage index, not probability. Geopolitical theory, historical analogy and regional context are **never evidence**.

## Quick start

1. `python -m unittest discover -s tests -v`
2. `python -m geowatch collect`
3. `python -m geowatch serve`
4. `python -m geowatch metrics`
5. `python -m geowatch consumer-feed --consumer agrolog`
6. `python -m geowatch dispatch-alerts`

Optional PostgreSQL/GCS dependencies: `pip install '.[production]'`.

## API

Compatibility endpoints remain:
- `GET /v1/feed`
- `GET /v1/reports/latest`

Episode/product/validation API:
- `GET /v2/feed`
- `GET /v2/reports/latest`
- `GET /v2/episodes?country=&state=&since=&min_strength=&limit=`
- `GET /v2/episodes/{episode_id}`
- `GET /v2/events?country=&since=&limit=`
- `GET /v2/changes?since=&limit=`
- `GET /v2/map?limit=`
- `GET /v2/alerts/pending?limit=`
- `GET /v2/consumers/agrolog/feed`
- `GET /v2/review-queue`
- `GET /v2/coverage`
- `GET /v2/operational`
- `GET /metrics`
- `GET /health`
- `GET /dashboard`

Set `GEOWATCH_API_TOKEN` before exposing data endpoints outside a trusted boundary.

## Deployment state

`scripts/deploy_gcp.sh` contains Cloud Run/API/collector/dispatcher/Scheduler/GCS deployment assets, but repository presence does **not** mean a live cloud deployment exists. Production remains an external gate requiring a GCP project, PostgreSQL/PostGIS, secrets and end-to-end smoke/restore validation.

## Release state

- v0.3 standalone baseline — complete.
- v0.4 history/quality — complete.
- v0.5 convergence engine — complete.
- v0.6 operational data layer — complete in code/CI; live deployment external.
- v0.7 product/alert layer — complete, CI passed and merged.
- v0.8 geopolitical knowledge + validation — **complete, CI passed and merged in PR #6**.
