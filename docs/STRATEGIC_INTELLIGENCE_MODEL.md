# Strategic Intelligence & Learning Model

## Purpose

Geopolitical Watch v0.9 extends monitoring into structured strategic intelligence without allowing analytical context to contaminate factual evidence.

The permanent separation is:

`observed evidence -> claims/events -> conflict episode -> strategic context -> hypotheses/forecast -> outcome/review -> learning proposal`

Knowledge, theory, country profiles, graph edges, escalation indicators, sanctions context and historical analogies are analytical context. They do not verify an event or attribution and do not increase `EvidenceStrength`.

## Strategic memory

The primary database now contains an auditable strategic ledger for:

- analyst review decisions;
- episode merge/split/revert operations;
- probabilistic forecasts and resolutions;
- proposed knowledge updates.

A learning proposal can be produced from repeated reviewed decisions, but `auto_apply=false` is permanent. A knowledge mutation requires provenance, review and a versioned change.

## Country strategic profiles

`config/geopolitics/country_profiles.json` stores structural profiles rather than political-officeholder snapshots. Each profile can contain:

- strategic regions;
- persistent strategic themes;
- economic/security exposures;
- analytical questions;
- canonical source IDs.

Volatile quantitative fields should be loaded from dated source datasets instead of hard-coded profiles.

## Temporal strategic graph

`config/geopolitics/strategic_graph.json` represents typed relations among countries, organizations, chokepoints and strategic regions. Every edge requires:

- source and target;
- typed relation;
- source reference;
- validity window;
- refresh cadence when volatile.

Graph relations are context, not evidence of an event or future action.

## Escalation indicator library

The indicator engine tracks observable patterns such as mobilization, force reinforcement, diplomatic drawdown, air/maritime restrictions, strategic-infrastructure attack reports, cross-border strikes, ceasefire collapse, sanctions pressure, nuclear-posture language, backchannel talks, ceasefires, withdrawal and infrastructure restoration.

Indicator weights are diagnostic triage points, not probabilities. Baselines, routine exercises, rotations and precautionary actions must be considered.

## Competing hypotheses

Analysts can maintain multiple hypotheses for the same episode. Each hypothesis keeps:

- statement;
- indicators for;
- indicators against;
- discriminating indicators;
- assumptions.

Diagnostic scores rank fit to observed indicators but are explicitly not probabilities. The objective is to seek evidence that distinguishes explanations rather than only confirming a preferred narrative.

## Forecasting

Forecasts are immutable-at-creation objects with:

- subject and question;
- probability in [0,1];
- creation timestamp;
- horizon;
- rationale;
- later binary resolution and resolution rationale.

Calibration uses Brier score and probability bins. Forecast quality is evaluated historically; no single forecast score is treated as truth.

## Geoeconomic dependency

The initial quantitative layer provides:

- supplier concentration (HHI);
- effective number of suppliers;
- structural import dependency index;
- route concentration;
- chokepoint exposure share.

These are exposure metrics, not loss estimates. Inventories, spare capacity, contractual flexibility, substitution, insurance, freight and policy response remain separate drivers.

## Sanctions context

Sanctions objects preserve authority, regime, target, measure, effective date, revocation and source. Sanctions are legal/administrative facts within issuing jurisdictions, not generic geopolitical risk scores. Compliance interpretation requires specialist/legal review.

## Maritime notices

Navigational-warning context is normalized separately from conflict evidence and from future AIS context. An official warning can establish a navigation-safety restriction or hazard within its scope, but it does not by itself establish conflict attribution or intent.

## Merge/split workflow

Episode corrections are versioned operations.

### Merge

- snapshot all source episodes and claims;
- construct survivor;
- reassign/reconcile claims;
- recalculate state and evidence strength;
- close absorbed episodes with lineage;
- persist an operation snapshot.

### Split

- validate complete, non-overlapping event groups;
- construct deterministic child IDs;
- recompute child claims/evidence/state/strength;
- close source episode with lineage;
- persist operation snapshot.

### Revert

Rollback restores the prior snapshot and writes a new reversal operation. History is not deleted.

## Learning governance

Allowed automatic outputs:

- review queue item;
- calibration metric;
- knowledge proposal;
- alias/source-quality/methodology proposal.

Never automatic:

- actor attribution;
- factual claim rewrite;
- event deletion;
- historical record overwrite;
- conversion of diagnostic scores into probabilities;
- acceptance of a knowledge proposal.

## Release boundary

v0.9 implements the strategic-intelligence framework in code and CI. Live GCP deployment, source credentials, real sanctions feeds, official maritime-warning ingestion, large historical backfill and empirical forecast calibration remain operational/data gates rather than assumed accomplishments.
