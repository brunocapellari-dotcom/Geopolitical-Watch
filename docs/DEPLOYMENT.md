# Geopolitical-Watch deployment and development model

## Canonical source of truth

GitHub is the canonical source of truth for code, configuration, tests, infrastructure-as-code and release history.

No external environment is allowed to become the source of truth. Replit, Claude Code and Google Cloud must consume a Git commit that already exists in GitHub. Changes made during development must return to GitHub and pass the cumulative Full Project Gate before they can be considered part of the product.

## Release rule

A release is indivisible. The project does not promote isolated modules independently.

Before a commit can be promoted to `main` or used outside GitHub it must pass the complete repository gate, including:

- repository compilation;
- every JSON/configuration validation;
- import of every `geowatch` module;
- the complete unit/contract suite;
- deterministic evaluation fixtures;
- dependency audit;
- static security analysis;
- PostgreSQL/PostGIS and persistent RAW validation;
- strict production invariants;
- Terraform format/init/validate;
- production container build and non-root runtime test;
- authenticated Chromium/MapLibre smoke test;
- repository secret/misconfiguration scan;
- production image vulnerability scan.

A change in any part of the system requires the complete gate to run again.

## Environment roles

### GitHub

Primary engineering control plane:

- canonical repository;
- pull requests and review history;
- Full Project Gate;
- public-data integration validation;
- immutable release commit;
- GitHub OIDC federation to Google Cloud after production authorization.

### Google Cloud

Only production target.

Planned production services:

- Cloud Run for the private web/API service;
- Cloud Run Job + Cloud Scheduler for registry-driven collection/analysis ticks;
- Cloud SQL PostgreSQL/PostGIS as the canonical operational database;
- Cloud Storage for immutable RAW evidence and future PMTiles/basemap assets;
- Secret Manager for credentials;
- Artifact Registry for immutable production images;
- Workload Identity Federation for keyless GitHub deployment.

The Cloud SQL instance must be private-only. Public IPv4 is forbidden. Database transport must require encryption. Cloud Run service and collection job use Direct VPC egress to reach the private database.

No `terraform apply` is performed until the exact release commit is green and the infrastructure plan/cost has been reviewed.

### Replit

Development and visual inspection environment only.

Permitted uses:

- open an already-green GitHub branch/commit;
- inspect UI behavior;
- perform exploratory development;
- reproduce defects;
- propose changes that are committed back to GitHub.

Not permitted:

- become the production database;
- maintain a divergent production copy;
- deploy a branch that has not passed the GitHub Full Project Gate;
- hold production secrets as the canonical secret store.

### Claude Code

Engineering/review environment only.

Permitted uses:

- inspect an already-versioned repository state;
- code review;
- refactoring proposals;
- test generation;
- architecture critique;
- implementation work committed back to GitHub.

Claude Code must not create a parallel architecture, separate database or independent source of truth. Any accepted change returns to GitHub and restarts the complete gate.

## Database architecture

Production database: Google Cloud SQL PostgreSQL/PostGIS.

Local/test database: SQLite where explicitly supported plus PostgreSQL/PostGIS in the integration gate.

Production requirements:

- private IP only;
- TLS-enforced Cloud SQL configuration;
- dedicated VPC/subnet;
- Direct VPC egress from Cloud Run and Cloud Run Job;
- deletion protection;
- automated backups;
- point-in-time recovery;
- schema initialization is idempotent;
- RAW evidence remains immutable and is also preserved in Cloud Storage;
- no database credentials committed to GitHub, Replit or source files.

## Collection architecture

Collection and analysis are separated from the web service.

- source-specific cadence is governed by the Source Registry;
- Cloud Scheduler invokes a bounded Cloud Run Job;
- the internal registry determines which sources are actually due;
- only one production collection mode can be active;
- failure of one source must not silently mark other sources healthy;
- continuous AIS is optional and enabled only when a valid key and always-on compute are intentionally configured.

## Secrets

Production secrets belong in Google Secret Manager. GitHub receives only the minimum deployment federation configuration needed for OIDC/WIF. Long-lived Google service-account JSON keys are not part of the architecture.

Do not commit `.env`, Terraform secret tfvars, API keys, database passwords, private certificates or exported credentials.

## Promotion sequence

1. Work only in GitHub until the integrated branch is complete.
2. Run the Full Project Gate and public-data integration on that exact commit.
3. Merge only after every required gate is green.
4. Run the complete gate again on the exact `main` commit.
5. Only then allow Replit/Claude Code to consume that commit for development/review, or Google Cloud to consume it for deployment.
6. Produce and review `terraform plan` before any paid infrastructure change.
7. Apply infrastructure only after explicit production authorization.
8. Deploy the scanned image by immutable digest.
9. Run real production E2E, persistence, scheduler, backup/restore and source-health checks.
