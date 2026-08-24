# v0.11.0 release gate

## Acceleration delivered

- source-scoped credential/terms activation registry;
- deterministic historical backfill queue;
- bounded ReliefWeb historical collector;
- regional FIRMS operating areas;
- cross-source UCDP/ACLED reconciliation without forced consensus;
- UK sanctions normalization plus UN/OFAC/UK official-source registry;
- IHO/NAVAREA governance registry;
- production API smoke gate;
- dry-run-by-default Cloud SQL restore drill;
- source-rights matrix and consolidated v1 release audit;
- Tier-1 country enrichment to roughly 25 countries;
- expanded actor profiles;
- critical infrastructure expanded beyond chokepoints;
- historical crisis corpus expanded to roughly 78 cases;
- rolling OOS validation framework;
- readiness estimate updated to ~0.77 while all external hard gates remain false.

## Non-negotiable boundaries

- Source adapter availability is not source permission.
- A blocked credential/terms source blocks only itself, not the entire pipeline.
- Provider disagreement remains visible; reconciliation is not truth adjudication.
- FIRMS and navigational warnings are context, not attack attribution.
- Sanctions records establish the issuing authority's designation record; legal applicability requires jurisdiction-specific review.
- Critical-infrastructure importance does not establish current disruption.
- Historical corpus size does not equal gold-label quality.
- CI success is not production evidence.

## Release gate

Merge v0.11 only if the cumulative GitHub Actions suite passes the final head SHA. Live GCP smoke, restore/PITR, restricted-source credentials, large real-world OOS validation and final security/cost/source-rights evidence remain external hard gates for 95%/v1.0.
