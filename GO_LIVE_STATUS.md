# GO-LIVE STATUS — Geopolitical Watch

Updated: 2026-10-09

## Release candidate
- Branch: `stabilization/go-live-20261007`
- Target: `release/go-live-20260929`
- PR: #37
- Software-validated commit: `4541b8be5053a24ec7d7bb4b4aeb3c9682dd5d6b`
- Status: **BLOCKED_EXTERNAL**

## Verified on the exact software-validated commit

### Real source path
- `public-beta-integration` PR run 37879585755: PASS.
- `public-beta-integration` push run 37879579915: PASS.
- Real GDELT + GDACS collection, health assertion and operational intelligence build passed twice without code edits.

### Public/historical bootstrap
- `public-data-integration` run 37879585917: PASS.
- UCDP historical artifacts, review packets, empirical history, NGA WPI, UN/LOCODE crossmatch, World Bank baseline, bounded UN Comtrade, official sanctions and operational intelligence assets passed.

### Whole-project gate
- `full-project-gate` PR run 37879585848: PASS.
- `full-project-gate` push run 37879580014: PASS.
- This includes compile/import, full unit/contract/regression/adversarial suite, deterministic fixtures, dependency audit, Bandit, PostgreSQL/PostGIS + persistent RAW, strict production invariants, Terraform validation, production container build/non-root check and private HTTP + real browser MapLibre smoke.

### Security
- Repository secret/high-impact misconfiguration scan: PASS.
- Production container HIGH/CRITICAL fixed-vulnerability scan: PASS.
- External-content trust boundary, SSRF controls, XML entity-expansion rejection and isolated-hostile-browser contracts are tested.

### Core operational contracts now covered
- RAW evidence preservation and provenance.
- Event/claim/evidence separation.
- Dependency-aware source independence and syndication suppression.
- Source-health-gated material alerts.
- Geolocation provenance: reported/inferred/unknown + method/confidence.
- Entity raw-name/normalized-name/resolution-confidence provenance.
- Immutable point-in-time object/version ledger and `as_of` API.
- Claim verdict history.
- Non-causal event graph with PRECEDES/FOLLOWS/RELATED_TO; causal upgrades require evidence/review.
- Minimum API: events/detail, sources/source-health, actors, regions, timeline, alerts, health.
- Required UI routes: `/overview`, `/map`, `/events`, `/conflicts`, `/actors`, `/timeline`, `/alerts`, `/sources`, `/system`.
- Explicit adversarial cases: single fake report, conflicting evidence, incompatible geography, stale media repost, hostile/prompt-injection-like content and malformed payload.

## Remaining hard blockers

### BLOCKER GCP-01 — GitHub → GCP federation not activated for this repository
Impact:
- `gcp-cloudbuild-gate` fails before checkout.
- No Google Cloud deployment or Cloud Build execution can be certified from this repository.

Evidence:
- run 37879585714: FAIL at `Require Google Cloud federation variables`.
- run 37879579919: same failure.
- `GCP_PROJECT_ID` resolves to `ai-holding-prod-bc`; WIF provider and build/deploy service-account variables are absent.

Prepared solution:
- Terraform remains source of truth.
- `scripts/bootstrap_gcp_federation.sh` creates/plans the dedicated foundation safely, uses keyless WIF, rejects destructive foundation plans, and can publish the non-secret GitHub variables when `gh` is authenticated.
- The provider is restricted to the Geopolitical-Watch repository and explicit release refs.

Minimal human action:
1. Authenticate in Google Cloud Shell with an account authorized to create the reviewed foundation.
2. Check out this repository/branch.
3. Run the bootstrap first without `APPLY=1` and review the non-destructive plan.
4. Only after approving the billable foundation, run it with `APPLY=1`.

### BLOCKER GCP-02 — production deployment/smoke not yet executed
Impact:
- Cloud Run service/job, scheduler and exact image digest have not been proven live for this release candidate.

Solution after GCP-01:
- rerun `gcp-cloudbuild-gate`;
- publish scanned immutable image;
- apply reviewed runtime Terraform;
- execute one production source tick;
- smoke `/health`, authenticated API, dashboard/map and scheduler.

### BLOCKER RECOVERY-01 — production backup/PITR restore drill not yet passed
Impact:
- backup protection cannot be called validated.

Solution after live Cloud SQL exists:
- execute an isolated restore drill;
- validate schema/PostGIS, event/episode/claim/evidence/checkpoint integrity and API read path;
- record evidence;
- delete the drill instance.

## GO-LIVE rule

Do **not** merge this PR to the release branch and do **not** declare GO-LIVE until:
1. GCP federation is active;
2. the exact-head GCP Cloud Build gate passes;
3. live deployment smoke passes;
4. scheduler executes successfully;
5. production backup/PITR restore drill passes.

Software gates are green. External production gates remain blocking.
