# GO-LIVE STATUS — Geopolitical Watch

Updated: 2026-10-08

## Current release branch
- Branch: `stabilization/go-live-20261007`
- Target: `release/go-live-20260929`
- PR: #37
- Status: BLOCKED

## Verified
- Real public-source integration passes.
- Real public beta path passes for GDELT/GDACS.
- RAW preservation and canonical processing path execute in CI.
- Source-health gating is wired into material alerts.
- Dependency-aware source independence is implemented for duplicate/syndicated reporting.
- Immutable object-version ledger exists in SQLite and PostgreSQL/PostGIS for point-in-time reconstruction groundwork.
- Production container is configured for a non-root runtime.

## Open hard gates
1. `full-project-gate` must pass on the exact release head.
2. Google Cloud federation is not available to this repository yet:
   - `GCP_WIF_PROVIDER` missing.
   - deploy/build service account variable or secret missing.
3. Live Google Cloud deployment smoke has not passed on the release head.
4. Backup/PITR restore drill has not been executed successfully against production Cloud SQL.
5. Point-in-time history still requires final API/verdict persistence coverage and regression tests before being marked complete.

## GO-LIVE rule
Do not merge to the release branch or declare GO-LIVE until all hard gates above have evidence from the exact head commit.
