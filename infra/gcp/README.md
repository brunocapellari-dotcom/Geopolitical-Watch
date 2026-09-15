# Geopolitical-Watch — Google Cloud production

This directory is the final cloud target for the private Geopolitical-Watch website. It is infrastructure-as-code, not a prototype deployment.

## Architecture

- **Cloud Run service** — private application/API and dashboard shell. The Cloud Run URL is network-reachable so the application login works in a normal browser; all data routes remain protected by the signed application session/bearer contract. `/health` is intentionally public. IAP is a planned second authentication boundary after the first project-level OAuth/IAP bootstrap is authorized.
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

## Foundation-first bootstrap

The first deployment avoids the Artifact Registry/Cloud Run chicken-and-egg problem without introducing a second provisioning system.

`deploy_runtime=false` is the default. The first Terraform apply creates only the production foundation: APIs, VPC/private-services access, Cloud SQL/PostGIS, RAW bucket, Secret Manager containers/versions, Artifact Registry, service accounts and GitHub Workload Identity Federation. It does **not** create Cloud Run, the collection job or Scheduler.

After the foundation exists, set the non-secret GitHub WIF/project variables from Terraform outputs and run the single `gcp-production-release` workflow with `confirm=PUBLISH`. The workflow reruns the Full Project Gate, builds the exact `main` commit, scans the image, pushes it to Artifact Registry and prints the immutable digest. In `PUBLISH` mode it changes no Cloud Run runtime.

Use that digest as `TF_VAR_container_image`, set `TF_VAR_deploy_runtime=true`, review a second Terraform plan and apply it. This creates the runtime from the already-scanned image. Future releases use the same workflow with `confirm=DEPLOY`; only the image digest of the already-provisioned service/job is updated. Terraform intentionally ignores only those image fields so infrastructure configuration remains authoritative while GitHub release automation owns application-image promotion.

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

Foundation inputs:

```bash
export TF_VAR_project_id='YOUR-PROJECT-ID'
export TF_VAR_deploy_runtime='false'
export TF_VAR_api_token='A-RANDOM-SECRET-OF-AT-LEAST-32-CHARACTERS'
export TF_VAR_db_password='A-RANDOM-DATABASE-PASSWORD-OF-AT-LEAST-24-CHARACTERS'
# Optional only after AIS cost/terms approval:
export TF_VAR_aisstream_api_key='...'
```

Runtime activation adds:

```bash
export TF_VAR_deploy_runtime='true'
export TF_VAR_container_image='southamerica-east1-docker.pkg.dev/YOUR-PROJECT-ID/geowatch/geowatch@sha256:EXACT-SCANNED-DIGEST'
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
6. Run `terraform init -backend-config="bucket=STATE_BUCKET"` and a **foundation** plan with `deploy_runtime=false`.
7. Review cost/resources and apply only after explicit authorization. Record the WIF/provider/deployer outputs as non-secret GitHub repository variables.
8. Dispatch `gcp-production-release` from the exact green `main` commit with `confirm=PUBLISH`; record the immutable scanned image digest emitted in the workflow summary.
9. Set `TF_VAR_container_image` to that exact digest and `TF_VAR_deploy_runtime=true`; run and review the **runtime activation** plan, then apply it.
10. Confirm Cloud SQL has only private IP and PostGIS initializes; execute the scheduler job once manually; verify `/health`, login, `/v2/runtime/readiness`, `/v2/source-health`, the map layers and a complete browser smoke.
11. Perform a real backup/restore/PITR exercise before declaring production operational.
12. Future releases use `confirm=DEPLOY`, which reruns the full gate, rescans the exact image, promotes only its digest and runs a production source tick + health smoke.
13. Bootstrap Cloud Run IAP in the Google Cloud project if desired/required, grant the authorized Google identity, then model that finalized identity policy in Terraform.

No resource in this directory is created merely by committing these files. Applying Terraform can create billable resources, especially Cloud SQL and continuous AIS compute.
