# Roadmap

## v0.3–v0.10 — complete

The standalone baseline, history/quality, convergence engine, operational data layer, product/alerts, geopolitical knowledge, strategic learning and empirical-readiness layers are complete in code/CI. Live cloud operation remains a separate evidence gate.

## v0.11 — accelerated production and empirical validation — implemented pending CI

Delivered in this code wave:

1. production deployment assets retained and live smoke gate added;
2. non-destructive Cloud SQL restore-drill workflow added;
3. UCDP activation/backfill made source-scoped and executable when token/terms pass;
4. ReliefWeb bounded historical range pagination added, activation remains appname-gated;
5. FIRMS production policy moved to regional bounding boxes with sensor-attribution safeguards;
6. UCDP × ACLED reconciliation added without forcing provider agreement;
7. UN/OFAC/UK sanctions normalization/official-source registry expanded;
8. IHO/NAVAREA registry and web-vs-broadcast governance formalized;
9. Tier-1 country profiles accelerated to roughly 25 priority countries;
10. actor registry expanded across international/security/economic organizations and armed actors;
11. graph integrity audit added; relation/source/validity governance remains mandatory;
12. critical-infrastructure graph expanded beyond chokepoints into ports, energy terminals, pipelines and cable corridors;
13. historical crisis corpus expanded from ~40 to ~78 cases with layered source enrichment;
14. rolling out-of-sample forecast/alert/convergence reporting added;
15. source-rights/release/recovery audits consolidated for a v1 go/no-go gate.

The conservative weighted project-readiness estimate is now approximately **0.77**. This is project readiness, not analytical accuracy. The target cannot reach 0.95 until all external hard gates pass.

## External hard gates still open

- live GCP production smoke evidence;
- Cloud SQL restore/PITR drill evidence;
- credentials/terms approval for every enabled restricted source;
- large source-backed historical out-of-sample validation;
- final security, cost and source-rights audit evidence.

## Next 30 — accelerated path to v1.0

### Wave A — live data and recovery
1. Execute real GCP preflight with the target project and least-privilege identities.
2. Provision/validate Cloud SQL PostgreSQL/PostGIS production instance.
3. Execute authenticated Cloud Run API deployment and `production_smoke.sh`.
4. Execute collector Cloud Run Job against production storage/database.
5. Execute isolated Cloud SQL restore/PITR drill and record reconciliation evidence.
6. Activate UCDP after token + terms review; run first bounded backfill windows.
7. Activate ReliefWeb after approved appname; run bounded historical coverage audit.
8. Activate FIRMS MAP_KEY using regional areas; measure sensor false-context rate.
9. Activate ACLED after license/OAuth review; run bounded historical backfill.
10. Turn UN/OFAC/UK sanctions snapshots into scheduled change jobs with durable diffs.

### Wave B — empirical validation and historical depth
11. Build source-coverage dashboard with first/last reference date and gap detection.
12. Expand historical crisis corpus to at least 150 source-backed cases.
13. Enrich the first 100 cases with dated chronologies and explicit sources.
14. Build gold labels for episode merge/split decisions on historical data.
15. Run rolling convergence validation by year, region and source mix.
16. Run alert-policy precision/recall/FPR analysis by policy and region.
17. Build at least 200 resolved historical forecast questions from frozen templates.
18. Run Brier/calibration analysis by 1/7/30/90-day horizon.
19. Measure leading-indicator detection lead time and false-positive rates.
20. Produce mandatory postmortems for material false positives/negatives and forecast misses.

### Wave C — global strategic model and v1 release candidate
21. Reach Tier-2 country-profile enrichment target of at least 80%.
22. Expand actor profiles to at least 50 strategically relevant organizations/groups.
23. Expand official alliance/security-treaty graph with sourced validity intervals.
24. Add sourced territorial-dispute/rivalry relationships without encoding advocacy or legal conclusions.
25. Link sanctions regimes/designations to graph entities with jurisdiction/date semantics.
26. Expand critical-infrastructure graph toward 250+ strategic nodes with source metadata.
27. Attach dated trade/energy/agriculture observations to geoeconomic dependency calculations.
28. Produce chokepoint scenario packs with route-share exposure, alternatives and uncertainty bands.
29. Run load, cost, security, recovery and source-rights audits and close every v1 hard gate.
30. Cut a v1.0 release candidate only if readiness >=0.95 **and** every hard gate has evidence.

## v1.0 gate

v1.0 requires demonstrated production reliability, restore capability, empirically validated convergence/alert/forecast quality, stable API contracts, security/cost/source-rights review and documented knowledge governance.

## Later

AIS/ADS-B, prediction markets, additional satellite/context layers and other sensors enter only after terms, cost, privacy, stability, operational-security and false-positive risks are reviewed. They are not required for v1.0.
