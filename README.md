# Geopolitical Watch — Monitor de Conflitos

Private public-source geopolitical conflict monitoring and strategic-intelligence website.

## Current release

Version **0.16.0** extends the operational-intelligence platform with a canonical temporal Relationship model, explicit separation between observation time and real-world validity, a governed Research Gateway, an in-house Evidence Snapshot Service, a derived-only Temporal Graph Adapter and a read-only relationship API. It also hardens central HTTP retrieval against local/private IP literals. External tools discovered in the September review remain governed targets or references until a real adapter and full-project validation justify adding the dependency.

The codebase remains designed around evidence provenance, explicit uncertainty, strict separation between observed/reported/estimated/inferred information, resilient source collection, PostgreSQL/PostGIS production storage and a MapLibre global interface.

The project remains independent from AgroLog MT. Other projects may consume published high-level signals, but they do not share the Monitor's codebase or operational state.

## Permanent evidence rules

- `Event` is preserved evidence; `ConflictEpisode` is the persistent analytical unit.
- Knowledge, profiles, graph edges, historical analogies and infrastructure criticality are context, not event verification.
- GDACS and sensor/context feeds cannot seed conflict episodes or raise EvidenceStrength by themselves.
- Provider disagreements are preserved rather than forcibly reconciled.
- EvidenceStrength is a heuristic triage index, never a probability.
- Forecast probability never changes EvidenceStrength.
- Learning proposals never auto-apply.
- Research-coded history is not human gold or current evidence.
- Scenario packs are not forecasts.
- Missing economic observations are never silently zero-filled.
- Distinct resolved infrastructure identities cannot be merged merely because they are nearby or share country, region, claim type or time window.
- Public critical-infrastructure information is structural context only; the system does not model exploit paths or vulnerabilities.
- A selected aircraft/vessel trail contains only positions actually observed by the running backend; it is not a complete route or proof of origin/destination.

## Production architecture

`authorized public sources -> immutable RAW evidence -> PostgreSQL/PostGIS -> normalized events -> entity resolution -> convergence -> ConflictEpisodes -> verification -> operational state/deltas -> alerts/forecasts -> private MapLibre website`

The sole production target is Google Cloud:

- Cloud Run private website/API;
- Cloud Run Job + Cloud Scheduler for batch source collection;
- Cloud SQL PostgreSQL with PostGIS;
- Cloud Storage for durable RAW evidence and optional static map assets/PMTiles;
- Secret Manager for application and provider credentials;
- Artifact Registry for immutable container images;
- Workload Identity Federation for GitHub deployment without service-account JSON keys;
- a separate always-on execution path for continuous AIS when enabled.

Legacy alternative deployment descriptors are removed rather than maintained in parallel. A paid Replit VM may be used as a **temporary private runtime bridge** while GitHub-hosted runners/GCP bootstrap are unavailable; it must run the same repository, PostgreSQL/PostGIS schema, strict authentication and singleton scheduler contract. Google Cloud remains the canonical long-term production target.

## Private web interface

The site uses **MapLibre GL JS 6.9.1 through the supported ESM bundle** and a governed layer catalog in `config/map_layers.json`.

Each map layer declares:

- source/provenance;
- semantic class: `OBSERVADO`, `INFORMADO`, `ESTIMADO` or `INFERIDO`;
- evidentiary role (`evidence` or `context`);
- default visibility;
- refresh interval;
- freshness expectation;
- an operator-facing interpretation note.

Current governed layers are conflicts, critical infrastructure, physical context, network context, public aircraft observations and AIS vessels. Aircraft route context is not represented as a confirmed flight plan. AIS destination/ETA values are self-reported when present; vessel origin requires explicit historical inference.

Selecting an aircraft or vessel can draw a recent observed trail held by the running backend. Aircraft route context remains visually and semantically distinct from the observed trail. AIS static messages can enrich name/destination/ETA but cannot refresh a stale position timestamp.

The production dashboard is authenticated by a signed private session. Machine consumers may use the Bearer contract. Secrets are not embedded in browser JavaScript.

## Runtime and storage

Production structured storage is PostgreSQL/PostGIS. RAW evidence can be stored compressed in PostgreSQL or in GCS. Source freshness, checkpoints, provenance, source health and run history are preserved separately from analytical conclusions.

The production web process does not need to run the batch collector internally when the external Cloud Scheduler path is configured. This avoids duplicate collection and makes collection independently observable/retryable.

## Tool and dependency governance

`config/tooling_registry.json` is the decision registry for core tooling. The rule is one primary tool per capability unless two tools demonstrably cover different layers. Unused dependencies are forbidden and reference projects do not become code dependencies automatically.

Current primary choices remain MapLibre GL JS, PostgreSQL/PostGIS, Playwright, Trivy, pip-audit and AISStream. The September 2026 tooling review additionally selects Trafilatura and Crawl4AI for the future Research Gateway, Scrapling only as a bounded selector-resilience fallback, Browsertrix Crawler for selected high-fidelity evidence capture, Docling for complex document parsing, Graphiti only behind the derived Temporal Graph Adapter, Phoenix + Promptfoo for agent observability/regression, OPA + ToolHive for policy/isolation, OASIS STIX2 for boundary interoperability, and Martin only if measured map scale justifies a separate tile service. `pyais` is approved as a conditional raw-NMEA decoder only when a raw AIS source exists. AIS-catcher is an edge-receiver reference for future owned sensors and remains isolated from the server architecture. PMTiles is the accepted target for a self-hosted static basemap. AGPL reference projects such as WorldMonitor are studied for architecture and product ideas without copying their code into this proprietary repository.

`config/source_candidates.json` records high-value data candidates discovered during research. A candidate is promoted into the operational source registry only after endpoint, terms/license, cadence, parser, provenance and evidence-role review.

## Validation and release gate

A release is not accepted from a subset of tests. `.github/workflows/test.yml` executes the cumulative full-project gate against the exact commit.

The gate covers:

1. compilation of the repository;
2. validation of all JSON configuration;
3. import of every `geowatch` module;
4. the complete unit/contract suite with coverage;
5. deterministic clustering and episode fixtures at 100% precision/recall;
6. dependency vulnerability audit;
7. Bandit static security analysis;
8. real PostgreSQL/PostGIS plus persistent RAW round trip;
9. strict production runtime invariants;
10. Terraform formatting/init/validation;
11. production Docker build;
12. authenticated Chromium/Playwright MapLibre smoke test.

The workflow additionally scans the repository with Trivy for secrets and high-impact misconfiguration, then scans the resulting production container for fixed HIGH/CRITICAL OS and library vulnerabilities. The GCP release workflow rebuilds the exact commit, scans that exact image before publication, pushes it, resolves the immutable registry digest and deploys by digest.

GitHub Actions dependencies are pinned to immutable commit SHAs. Core workflows use current Node-24-compatible action generations.

## Public-source coverage

Credential-free or public upstreams already represented in the architecture include GDELT, GDACS, UCDP public bulk datasets, NGA World Port Index, World Bank, UN/UK sanctions, USGS, IODA/RIPEstat, UN LOCODE and bounded UN Comtrade workflows where applicable.

Restricted or credentialed sources remain disabled until their terms/credentials are explicitly approved. The existence of an adapter never implies authorization to collect a source.

Public aircraft observations use ADSB.lol through the private backend. AISStream integration is server-side only and remains inert without `AISSTREAM_API_KEY`.

The current candidate review also tracks POLECAT/PLOVER, SIPRI datasets, Airwars, CrisisWatch and COW/MID. They are not silently activated merely because they are valuable sources.

## Historical validation and forecasting

The repository contains historical conflict reconstruction, human-review queues, no-lookahead historical benchmarks, prospective forecast ledgers, calibration metrics and multi-horizon templates. Historical or research-coded data never impersonates a historical live prediction record.

Formal scientific readiness is a separate gate from software readiness. The repository must not claim validated intelligence accuracy merely because CI passes.

## Remaining external production gates

The repository can validate its software and infrastructure definitions, but it cannot self-certify external conditions. Final external evidence still includes live GCP smoke after deployment, database backup/restore/PITR drill, approved credentials/terms for each restricted source that is enabled, sufficient reviewed human-gold/out-of-sample evidence, and final operational cost/security/source-rights review.

Repository visibility and `main` branch protection are also account-level controls and must be enforced in GitHub before production deployment.

These gates are intentionally not inferred from repository code.
