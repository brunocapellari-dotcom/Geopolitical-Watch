# Geopolitical-Watch — Google Cloud production

This directory is the final cloud target for the private Geopolitical-Watch website. It is infrastructure-as-code, not a prototype deployment.

## Architecture

- **Cloud Run service** — private website/API. The Cloud Run URL is network-reachable so the application login works in a normal browser; all data routes remain protected by the signed application session/bearer contract. `/health` is intentionally public. IAP is a planned second authentication boundary after the first project-level OAuth/IAP bootstrap is authorized.
- **Cloud Run Job** — executes `python -m geowatch scheduler-tick` and exits. It performs only source work that is due according to the canonical source registry and then runs consolidated analysis when required.
- **Cloud Scheduler** — invokes the Cloud Run Job every five minutes by default. The registry controls the real per-source cadence, so this does not mean every source is fetched every five minutes.
- **Dedicated VPC + subnet** — Cloud Run service and job use Direct VPC egress for private-resource access.
- **Private Services Access** — reserves the service-networking range used by Cloud SQL private IP.
- **Cloud SQL PostgreSQL 18 + PostGIS** — canonical structured operational store. Public IPv4 is disabled, TLS encryption is required, backups and point-in-time recovery are enabled, and the application creates the idempotent PostGIS schema at runtime.
- **Cloud Storage** — immutable RAW evidence store with object versioning and storage-class transitions for cost control; objects are not automatically deleted.
- **Secret Manager** — site token, database password and optional AISStream key.
- **Artifact Registry** — private container registry.
- **GitHub Workload Identity Federation** — keyless deployment identity. No service-account JSON key is required.

## Environment governance

GitHub remains the source of truth. Google Cloud is production only. Replit and Claude Code are development/review environments only and must consume a GitHub commit that has already passed the complete project gate. No environment may keep a divergent canonical copy of code, schema or secrets.

## AIS cost gate

`enable_continuous_ais=false` by default. In this mode Cloud Run may scale to zero and continuous AIS is intentionally not claimed as available.

When `enable_continuous_ais=true`, the web service is constrained to exactly one instance, keeps one instance warm and sets `cpu_idle=false` so the AIS WebSocket collector can continue between HTTP requests. This creates continuous Cloud Run compute cost and must not be enabled until the cost is explicitly approved and `AISSTREAM_API_KEY` is supplied.

The one-instance constraint is deliberate: the current AIS live state is process-local, so horizontal scaling would create inconsistent snapshots and duplicate provider connections. Historical/persistent AIS can later be added to PostgreSQL without changing the public API contract.

## Region

The default is `southamerica-east1` (São Paulo). Change it before first creation if another region is required; moving stateful resources later is more disruptive.

## Network security

The production database is not internet-addressable:

- `ipv4_enabled=false` on Cloud SQL;
- a dedicated VPC and regional subnet are created for the Monitor;
- Private Services Access connects the VPC to Cloud SQL;
- Cloud Run and the collection job use Direct VPC egress;
- Cloud SQL requires `ENCRYPTED_ONLY` connections;
- no authorized public database networks are part of the architecture.

The private subnet CIDR defaults to `10.24.0.0/24` and must be checked for overlap against the actual GCP project before the first apply.

## Secrets and Terraform state

`api_token`, `db_password` and `aisstream_api_key` are sensitive Terraform variables. Provider write-only fields (`secret_data_wo` and `password_wo`) are used so the secret payloads are not persisted in Terraform state by these resources.

Terraform state still contains sensitive infrastructure metadata and remains protected. Never commit `.tfstate`, `.tfvars` or secret files. Use the private, versioned GCS backend with public-access prevention. `backend.tf` intentionally leaves the bucket name unset while fixing the canonical state prefix; the state bucket is supplied at `terraform init` time.

Recommended environment inputs:

```bash
export TF_VAR_project_id='YOUR-PROJECT-ID'
export TF_VAR_container_image='southamerica-east1-docker.pkg.dev/YOUR-PROJECT-ID/geowatch/geowatch:INITIAL-TAG'
export TF_VAR_api_token='A-RANDOM-SECRET-OF-AT-LEAST-32-CHARACTERS'
export TF_VAR_db_password='A-RANDOM-DATABASE-PASSWORD-OF-AT-LEAST-24-CHARACTERS'
# Optional only after AIS cost/terms approval:
export TF_VAR_aisstream_api_key='...'
```

Do not put those values in `terraform.tfvars` in the repository.

## Pre-deployment gate

Infrastructure must not be applied until the repository-wide release gate passes. The gate includes the entire Python test suite, deterministic evaluation, dependency/security scans, repository secret/misconfiguration scan, PostgreSQL/PostGIS integration, strict production startup, browser dashboard smoke, Docker build/runtime, production-image vulnerability scan and Terraform validation.

## First deployment sequence

1. Finish and merge the exact integrated release only after all GitHub gates pass.
2. Run the complete gate again on the exact `main` commit.
3. Create or select the dedicated GCP project and confirm billing only after the code gate is green.
4. Confirm the proposed subnet does not overlap another project network.
5. Create a private/versioned GCS Terraform-state bucket with public-access prevention and authenticate Terraform using an explicitly authorized identity.
6. Build the exact green Git commit into Artifact Registry and use an immutable image digest for `container_image`.
7. Run `terraform init -backend-config="bucket=STATE_BUCKET"` and `terraform plan`.
8. Review the complete plan and recurring-cost changes. Only then run `terraform apply`.
9. Confirm Cloud SQL has only private IP and PostGIS initializes; execute the scheduler job once manually; verify `/health`, login, `/v2/runtime/readiness`, `/v2/source-health`, the map layers and a complete browser smoke.
10. Perform a real backup/restore/PITR exercise before declaring production operational.
11. Set the non-secret GitHub repository variables from Terraform outputs (`GCP_WIF_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`, `GCP_PROJECT_ID`, `GCP_REGION`). Future releases can then publish without stored Google service-account keys.
12. Bootstrap Cloud Run IAP in the Google Cloud project if desired/required, grant the authorized Google identity, then model that finalized identity policy in Terraform.

No resource in this directory is created merely by committing these files. Applying Terraform can create billable resources, especially Cloud SQL and continuous AIS compute.
