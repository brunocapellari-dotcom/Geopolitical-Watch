# v0.9.0 release gate

## Strategic intelligence delivered

- durable analyst-review decision ledger;
- versioned merge/split/revert operations with snapshots and lineage;
- probabilistic forecast objects and resolution history;
- Brier-score and calibration-table evaluation;
- governed learning proposals from repeated reviewed decisions;
- country strategic profile framework and initial seed profiles;
- temporal strategic relationship/chokepoint graph;
- escalation/de-escalation indicator library;
- competing-hypotheses objects and diagnostic scoring;
- geoeconomic concentration/dependency/chokepoint metrics;
- sanctions normalization model with official-source registry;
- maritime navigational-warning normalization model with official-source registry;
- strategic graph and escalation context in episode reports/API;
- read-only strategic API endpoints;
- CLI commands for review, forecast, merge/split and rollback.

## Evidence boundary

The following never increase `EvidenceStrength` merely by existing:

- geopolitical theory;
- country strategic profile;
- strategic-graph edge;
- historical analogy;
- escalation indicator;
- hypothesis score;
- forecast probability;
- sanctions context beyond its issuing legal record;
- maritime warning beyond its navigation-safety scope.

## Release gate

The release may be merged only if the cumulative GitHub Actions test suite succeeds on the final head SHA.

Live GCP deployment and real-source credential activation remain separate operational gates. v0.9 code/CI does not imply production operation or empirical forecasting performance on a large historical corpus.
