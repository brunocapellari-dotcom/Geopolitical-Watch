# Roadmap

## v0.3–v0.10 — complete

The standalone baseline, history/quality, convergence engine, operational data layer, product/alerts, geopolitical knowledge, strategic learning and empirical-readiness layers are complete in code/CI. Live cloud operation remains a separate evidence gate.

## v0.11 — accelerated production and empirical validation — complete

Delivered:

1. production deployment assets retained and live smoke gate added;
2. non-destructive Cloud SQL restore-drill workflow added;
3. UCDP activation/backfill made source-scoped;
4. ReliefWeb bounded historical range pagination added, activation remains appname-gated;
5. FIRMS production policy moved to regional bounding boxes with sensor-attribution safeguards;
6. UCDP × ACLED reconciliation added without forcing provider agreement;
7. UN/OFAC/UK sanctions normalization/official-source registry expanded;
8. IHO/NAVAREA registry and web-vs-broadcast governance formalized;
9. Tier-1 country profiles accelerated;
10. actor and critical-infrastructure registries expanded;
11. rolling out-of-sample framework and source-rights/release/recovery audits added.

## v0.12 — reliable public Beta and empirical history — release candidate

Delivered in the acceleration wave:

1. credential-free public Beta separated from production configuration;
2. hourly Beta persistence via a versioned SQLite cache with concurrency control;
3. fail-closed workflow execution using `pipefail` and explicit script bootstrap;
4. live PR integration smoke against GDELT + GDACS;
5. transient HTTP retry/backoff for 429/5xx/network failures;
6. Beta health split between transient degradation and structural parser/schema/configuration failure;
7. explicit conflict-coverage availability separate from generic pipeline health;
8. context-only policy: GDACS and sensor signals cannot seed `ConflictEpisode` or conflict claims;
9. context-only signals cannot refresh conflict state or raise EvidenceStrength by themselves;
10. pre-fix Beta cache invalidated to prevent contaminated episode persistence;
11. concise operator digest with health, freshness, priority episodes and change flags;
12. live public-data integration gate for UCDP bulk, WPI, World Bank and official sanctions;
13. UCDP 26.1 parsing corrected against current codebooks, including continuous-episode reconstruction;
14. live UCDP bootstrap validated at 2,816 conflict-year rows, 628 continuous episodes, 303 conflict IDs and 1,928 actors;
15. layered empirical-history catalog added, keeping project-curated and UCDP research-coded cases distinct;
16. UCDP historical outcomes hidden when replay cutoff precedes resolution;
17. UCDP forecasting baseline restricted to outcome classes actually represented by the termination dataset;
18. deterministic identity labels remain explicitly pre-gold, never human-gold;
19. NGA World Port Index live validation produces 3,807 source rows and 300 structural candidates;
20. World Bank live validation covers 217 countries and 4,860 recent observations across five indicators;
21. sanctions normalization separates raw/name rows from unique provider IDs;
22. validated public snapshots contain 1,011 UN consolidated IDs and 6,334 UK Unique IDs;
23. scheduled UCDP/WPI/World Bank/sanctions refreshes hardened against false-green `tee` behavior;
24. public data and Beta artifacts retain RAW/report/database evidence for audit;
25. package/API version promoted to 0.12.0 from a canonical package version;
26. readiness dimensions recalculated conservatively to approximately 0.82 while all external hard gates remain false.

The public Beta is an initial usable operating path, not a substitute for final production. A run may remain operational while temporarily degraded by provider rate limiting, but it must state when conflict-source coverage is unavailable.

## External hard gates still open

- live GCP production smoke evidence;
- Cloud SQL restore/PITR drill evidence;
- credentials/terms approval for every enabled restricted source;
- large source-backed historical out-of-sample validation with reviewed gold labels;
- final security, cost and source-rights audit evidence.

## Accelerated path to v1.0

### Wave A — production and restricted sources
1. Execute real GCP preflight with target project and least-privilege identities.
2. Provision/validate Cloud SQL PostgreSQL/PostGIS production instance.
3. Execute authenticated Cloud Run API deployment and `production_smoke.sh`.
4. Execute collector Cloud Run Job against production storage/database.
5. Execute isolated Cloud SQL restore/PITR drill and record reconciliation evidence.
6. Activate tokenized UCDP API only if needed after terms review; public bulk history remains available independently.
7. Activate ReliefWeb after approved appname and run bounded historical coverage audit.
8. Activate FIRMS MAP_KEY using regional areas and quantify false-context rate.
9. Activate ACLED after license/OAuth review and run bounded reconciliation/backfill.
10. Validate a concrete OFAC SLS export/API endpoint before automated ingestion.

### Wave B — empirical validation and model quality
11. Persist long-run source-coverage/gap history instead of bounded-run summaries only.
12. Enrich the layered empirical corpus with dated source-backed chronologies.
13. Build reviewed human-gold labels for episode merge/split and conflict-vs-context decisions.
14. Run rolling convergence validation by year, region and source mix.
15. Run alert-policy precision/recall/FPR and alert-fatigue analysis.
16. Build at least 200 resolved historical forecast questions from frozen templates.
17. Run Brier/calibration analysis by supported outcome and forecast horizon.
18. Measure leading-indicator lead time and false-positive rates.
19. Add mandatory postmortems for material false positives/negatives and forecast misses.
20. Backtest source-degradation behavior and stale-data handling.

### Wave C — strategic coverage and v1 release candidate
21. Reach Tier-2 country-profile enrichment target of at least 80%.
22. Expand reviewed actor profiles to at least 50 strategically relevant organizations/groups beyond bulk aliases.
23. Expand sourced alliance/security-treaty graph with validity intervals.
24. Add sourced territorial-dispute/rivalry relationships without advocacy or legal conclusions.
25. Link sanctions regimes/designations to graph entities with jurisdiction/date semantics.
26. Promote WPI candidates into a reviewed critical-infrastructure layer using additional authoritative sources.
27. Attach dated trade/energy/agriculture observations to geoeconomic dependency calculations.
28. Produce chokepoint scenario packs with route-share exposure, alternatives and uncertainty bands.
29. Run load, cost, security, recovery and source-rights audits and close every v1 hard gate.
30. Cut v1.0 release candidate only if readiness >=0.95 **and** every hard gate has evidence.

## v1.0 gate

v1.0 requires demonstrated production reliability, restore capability, empirically validated convergence/alert/forecast quality, stable API contracts, security/cost/source-rights review and documented knowledge governance.

## Later

AIS/ADS-B, prediction markets, additional satellite/context layers and other sensors enter only after terms, cost, privacy, stability, operational-security and false-positive risks are reviewed. They are not required for v1.0.
