# Geopolitical Watch v0.13 — Operational Intelligence

## Purpose

v0.13 moves the public Beta from a current-state monitor toward a continuously auditable operational-intelligence product. It does not claim final production readiness.

## Delivered

1. Persistent operational snapshots and bounded run history.
2. Operational health classes: healthy, degraded, stale, partial and failed.
3. Run-to-run deltas for episode state, new flags, evidence-strength shifts and source status.
4. Operator digest enriched with the delta from the previous run.
5. The 628 UCDP research-coded continuous episodes remain available as the empirical layer.
6. 150 prioritized UCDP chronologies with preserved source IDs.
7. Up to 500 explicit human-gold review candidates; none are automatically labelled human-gold.
8. Rolling temporal validation now reports year, region and source-mix slices.
9. Frozen historical forecast bank target >=200, generated only from information before each target episode.
10. Forecast horizons 1/7/30/90 days, restricted to objectively supported outcome labels.
11. Tier-2 country strategic profiles enriched to the >=80% target and actor library expanded to >=50 profiles.
12. WPI promotion-review framework; a single structural source cannot establish reviewed geopolitical criticality or live status.
13. World Bank observations are attached as dated geoeconomic country context; bilateral dependency utilities preserve missing data rather than zero-fill it.
14. Five chokepoint scenario templates: Hormuz, Bab el-Mandeb/Suez, Malacca, Panama, and Turkish Straits.
15. Explicit v1 go/no-go using release-audit evidence; production/restore/human-gold/security gates remain false until demonstrated.

## Governance

- Historical research-coded data is not current event evidence.
- Gold-review candidates are not gold labels.
- EvidenceStrength is not probability.
- Structural infrastructure importance is not current disruption.
- Scenario packs are not forecasts.
- Missing geoeconomic observations are not assumed to be zero.
- Repository code/CI cannot self-attest production smoke, PITR restore, license approval, human review or final security audit.

## Readiness

The conservative weighted v0.13 software/project-state estimate is approximately 0.86. This is readiness, not analytical accuracy. The 0.95 target remains impossible while any hard gate is false.

## Release gate

Before merge, the release must pass:

- cumulative unit/regression tests;
- live public-data integration against UCDP/WPI/World Bank/UN/UK upstreams;
- live public Beta GDELT/GDACS integration where triggered;
- v0.13 operational-asset assertions.
