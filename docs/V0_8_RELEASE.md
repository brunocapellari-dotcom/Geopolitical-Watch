# v0.8.0 release gate

## Delivered

- deep geopolitical curriculum and knowledge governance
- structured knowledge graph seed for schools, concepts, regions and historical cases
- canonical source registry separating legal/official/academic/bibliographic material
- deterministic geopolitical context engine
- strict `context_not_evidence=true` output contract
- strategic context in episode reports and API detail
- multi-theory lenses and analytical questions
- historical analogies with explicit limits
- source coverage inventory
- analyst review queue generation
- episode-quality flags
- binary alert calibration metrics
- merge lineage and safe split planning
- API endpoints `/v2/coverage` and `/v2/review-queue`
- v0.8 regression suite

## Safety and epistemic boundary

Geopolitical knowledge cannot verify an event, increase `EvidenceStrength`, create military attribution, or override claim/evidence lineage. It provides structured analytical context only.

## Copyright boundary

Canonical books and copyrighted research are stored only as bibliographic metadata and original summaries/notes. The repository does not mirror full copyrighted works.

## External operational gates

The following remain external rather than falsely marked complete:

- live GCP deployment;
- production Cloud SQL/PostGIS backup/PITR restore drill;
- credentialed UCDP/ReliefWeb/FIRMS/ACLED activation;
- real historical backfill at scale.

## Release criterion

v0.8.0 is merged only after the full GitHub Actions test suite passes on the release PR.
