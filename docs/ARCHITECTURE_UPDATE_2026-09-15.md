# Geopolitical Watch — Architectural Update 2026-09-15

## Status vocabulary

- **ACTIVE**: implemented and allowed to run with the current governance contract.
- **BLOCKED**: implementation exists or is selected, but credentials, terms, licensing or a production prerequisite is missing.
- **PARTIAL**: useful implementation exists but required coverage is incomplete.
- **PLANNED**: architecture/registry entry exists but the collector or analytical integration is not implemented.
- **REFERENCE**: discovery/architecture reference only; never evidence authority.

No source becomes ACTIVE merely because it appears in the Source Registry.

## Canonical pipeline

`Source Registry -> source-specific collector / isolated browser -> immutable RAW archive -> hash/provenance ledger -> normalization -> Claim -> timestamp/geolocation/source independence/physical evidence -> Verdict Engine -> episode -> specialist AI assessment -> GEOPOLITICAL CHIEF AI -> map/alerts/report`

The verification layer is independent from the specialist analysis layer. Specialist AIs can propose claims and interpretations; they cannot grant themselves a stronger verdict.

## Audit matrix

| Domain | Status | Current capability | Required next work |
|---|---|---|---|
| News | PARTIAL | GDELT collection, publisher-aware clustering and provenance | Broaden registered publisher/official feeds and add explicit news-source health by publisher |
| ACLED | BLOCKED | Adapter and cursor collection exist | Align runtime credentials with current myACLED OAuth, complete terms review, activate only with credentials |
| GDELT | ACTIVE | Incremental collection, raw evidence, checkpoints, clustering | Registry-driven cadence activation and publisher-quality expansion |
| UCDP | BLOCKED | GED adapter/backfill exists | Credentials/terms/version gate and scheduled activation |
| AIS | BLOCKED | AISStream continuous collector and map layer exist | AISSTREAM_API_KEY, always-on runtime, persistent vessel trail/port-call history |
| ADS-B | PARTIAL | ADSB.lol live backend and route context exist | ADS-B Exchange/OpenSky rights review and optional adapters; persistent history only if terms permit |
| Satellite | PARTIAL | FIRMS sensor path and satellite role exist | Copernicus Data Space/EMS, CelesTrak and Space-Track collectors and source-specific verification |
| FIRMS | BLOCKED | Collector/parser exists; thermal anomalies are sensor context only | FIRMS_MAP_KEY and activation; key is now redacted from provenance/logs |
| Infrastructure | PARTIAL | Static strategic graph + WPI runtime support + taxonomy | OSM/Overpass and official datasets; expand public nodes with provenance, never vulnerability targeting |
| BGP | PLANNED | RIPEstat registered | Implement BGP collector, normalization, anomaly baseline and CYBER/NETWORK AI interpretation |
| Internet | PLANNED | IODA registered | Implement outage/reachability collector and baseline comparison |
| Humanitarian | PARTIAL | GDACS active; ReliefWeb adapter exists | Activate ReliefWeb after terms/appname; implement HDX, IOM DTM and ACAPS |
| Sanctions | ACTIVE | UN/OFAC/UK parsing and designation-diff support | Add source freshness/status to unified Source Registry health |
| OSINT | PARTIAL | Hostile-content security boundary exists | Build isolated Telegram/public-web collectors only after sandbox/browser-isolation gate |
| Maps | PARTIAL | Conflict, infrastructure, aircraft and AIS layers exist | Add BGP/internet/satellite/humanitarian layers as their collectors become real |
| Alerts | PARTIAL | Episode/change policy alerting exists | Add canonical Verdict thresholds and source-health suppression rules |
| Verification | PARTIAL | Claims/evidence/reconciliation + deterministic Verdict Engine | Integrate verdict persistence/API/UI and calibrate thresholds on reviewed historical cases |

## Source Registry

`config/source_registry.json` is the operational catalog. Every source records:

- source ID and domain;
- owner AI;
- runtime mode;
- target cadence;
- activation state;
- implementation state;
- required credentials;
- terms/licensing gate;
- evidence role;
- content trust classification;
- browser-isolation requirement;
- backfill capability.

ConflictWatch and SignalTrace are **REFERENCE** entries only. They can suggest upstream sources or architecture patterns, but they cannot corroborate a claim simply by being catalogs/dashboard projects.

## AI separation of duties

The canonical roles are:

1. GEOPOLITICAL CHIEF AI
2. NEWS INTELLIGENCE AI
3. OSINT AI
4. GEOINT AI
5. AVIATION AI
6. MARITIME AI
7. SATELLITE AI
8. INFRASTRUCTURE AI
9. CYBER/NETWORK AI
10. CONFLICT AI
11. HUMANITARIAN AI
12. VERIFICATION AI

Their contracts live in `config/ai_roles.json`. The Chief AI synthesizes; VERIFICATION AI owns the canonical evidence verdict; raw evidence is outside both agents' mutation authority.

## Verdict Engine

Canonical states:

- **CONFIRMADO** — requires independent corroboration plus physical or official evidence and adequate temporal/geospatial quality, with no credible refutation.
- **PROVÁVEL** — meaningful corroboration exists but the full confirmation gate is not met.
- **NÃO VERIFICADO** — insufficient evidence for a stronger conclusion.
- **CONFLITANTE** — credible supporting and refuting evidence coexist.
- **FALSO** — reserved for explicit retraction or strong independent refutation; lack of evidence alone never means false.

The deterministic implementation is `geowatch/verdict.py`. Confidence and factors are stored separately from the verdict so a user can see why the engine reached a state.

## Operational event contract

Every relevant event must be renderable as:

- **O QUE / what**
- **ONDE / where**
- **QUANDO / when**
- **QUEM / who**
- **FONTE / source**
- **EVIDÊNCIA / evidence**
- **CONFIANÇA / confidence**
- **STATUS / canonical verdict**

Unknown fields remain unknown; the system must not fill gaps with inference unless the field is explicitly labeled inferred.

## Hostile OSINT security boundary

All external sites, posts, Telegram content, documents and feeds are untrusted data. Source content must never become executable instructions to the system.

Mandatory controls:

- prompt-injection markers are surfaced but never obeyed;
- HTML is reduced to text; scripts, iframes, objects, forms and embeds are discarded;
- only HTTP(S) external URLs are accepted;
- localhost, loopback, link-local and private IP literals are rejected;
- collectors can enforce exact host allowlists;
- tracking parameters are removed from evidence URLs;
- credentials embedded in URLs are forbidden;
- runtime secrets are redacted before logs/provenance persistence;
- downloads are quarantined as non-executable content and have size/hash metadata;
- interactive hostile pages require an isolated browser boundary before a collector can be activated;
- no command, tool request or credential request contained in source data is authoritative.

## Evidence integrity

RAW payload bytes are immutable by `(source_id, sha256)` in production PostgreSQL. The evidence ledger records observations separately so repeat sightings do not overwrite historical bytes.

Production ledger fields include:

- raw payload;
- SHA-256;
- source;
- observed timestamp;
- collector ID;
- provenance-safe source URL;
- raw reference;
- bytes;
- first seen;
- last seen;
- first/last collector;
- observation count.

Local development maintains an append-only JSONL observation ledger plus a derived first/last-seen index. GCS stores immutable observation records; PostgreSQL is the initial authoritative production index for first/last-seen queries.

## Critical infrastructure

The required public strategic taxonomy is maintained in `config/geopolitics/infrastructure_taxonomy.json`:

- bases;
- ports;
- airports;
- nuclear facilities;
- power/energy;
- refineries;
- pipelines;
- submarine cables;
- telecom;
- bridges;
- straits.

Structural presence is not operational status. Public infrastructure intelligence is for strategic situational awareness; the platform must not generate exploit paths, attack vulnerability rankings or targeting guidance.

## Autonomous collection

`geowatch/collector_scheduler.py` is the registry-driven scheduler contract. It computes due sources from each source cadence and checkpoint and isolates failures by source. `geowatch/source_collection.py` provides single-source collection for existing batch adapters.

The scheduler is deliberately **not enabled in production yet**. Enabling it before integration tests would run two scheduling systems alongside the legacy embedded collector and create needless duplicate collection. Production activation must happen only after the analysis cycle is separated cleanly from collection and the repository gate passes.

## Deployment gate

This architecture update does not authorize Replit deployment by itself. Before paid/runtime activation:

1. repository tests must run successfully again;
2. Source Registry and AI-role contract tests must pass;
3. PostgreSQL/PostGIS and raw evidence ledger must pass integration smoke;
4. secret-redaction regression tests must pass;
5. hostile-content/SSRF tests must pass;
6. the autonomous scheduler must not run concurrently with the legacy global collector;
7. production credentials/terms must be reviewed source by source;
8. only then should runtime-specific validation consume Replit resources.
