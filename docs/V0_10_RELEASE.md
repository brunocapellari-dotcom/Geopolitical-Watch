# v0.10.0 release gate

## Delivered

- global country/territory namespace coverage with enrichment status;
- actor-profile registry;
- security-system relationship model;
- critical-infrastructure/chokepoint graph;
- dated geoeconomic observation contract;
- chokepoint exposure engine;
- sanctions feed normalization for official records;
- maritime-warning normalization;
- frozen forecast templates and multi-horizon forecasts;
- temporal no-lookahead backtest validation;
- historical crisis seed corpus;
- leading-indicator lead-time framework;
- post-event learning/postmortem objects;
- readiness matrix and v1 preflight;
- read-only v0.10 API surfaces;
- regression tests.

## Evidence discipline

None of the following verifies a conflict event by itself: country profile, actor profile, alliance membership, infrastructure criticality, route exposure, historical analogy, indicator hit, forecast probability, sanctions context beyond the issuing record, or navigational warning beyond its stated safety scope.

## Source validation notes

- UNSC Consolidated List provides current official consolidated sanctions records and change history in structured formats.
- OFAC Sanctions List Service is the primary OFAC public delivery surface for list data.
- IHO WWNWS links operational NAVAREA coordinators and explicitly warns that web publication does not replace approved maritime broadcast systems.

## Readiness baseline

The conservative v0.10 weighted project-readiness estimate is ~0.71. This is not analytical accuracy. It deliberately penalizes the project for missing production deployment, credentials/terms, restore validation, large historical out-of-sample testing and final security/source-rights audit.

A 0.95 readiness result is invalid unless every hard gate in `config/readiness.json` passes.

## Release gate result

The cumulative GitHub Actions test suite passed on PR #10 and v0.10.0 was merged to `main`.

Live GCP deployment, source credentials and large historical empirical validation remain external gates and are not implied by passing CI.
