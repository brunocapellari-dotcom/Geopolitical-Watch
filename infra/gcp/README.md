# Geopolitical-Watch — Google Cloud production

This directory is the final cloud target for the private Geopolitical-Watch website. It is infrastructure-as-code, not a prototype deployment.

## Architecture

- **Cloud Run service** — private website/API. The Cloud Run URL is network-reachable so the application login works in a normal browser; all data routes remain protected by the signed application session/bearer contract. `/health` is intentionally public.
- **Cloud Run Job** — executes `python -m geowatch scheduler-tick` and exits. It performs only source work that is due according to the canonical source registry and then runs consolidated analysis when required.
- **Cloud Scheduler** — invokes the Cloud Run Job every five minutes by default. The registry controls the real per-source cadence, so this does not mean every source is fetched every five minutes.
- **Cloud SQL PostgreSQL 18 + PostGIS** — canonical structured operational store. The application creates the idempotent PostGIS schema at runtime.
- **Cloud Storage** — immutable RAW evidence store with object versioning and storage-class transitions for cost control; objects are not automatically deleted.
- **Secret Manager** — site token, database password and optional AISStream key.
- **Artifact Registry** — private container registry.
- **GitHub Workload Identity Federation** — keyless deployment identity. No service-account JSON key is required.

## AIS cost gate

`enable_continuous_ais=false` by default. In this mode Cloud Run may scale to zero and continuous AIS is intentionally not claimed as available.

When `enable_continuous_ais=true`, the web service is constrained to exactly one instance, keeps one instance warm and sets `cpu_idle=false` so the AIS WebSocket collector can continue between HTTP requests. This creates continuous Cloud Run compute cost and must not be enabled until the cost is explicitly approved and `AISSTREAM_API_KEY` is supplied.

The one-instance constraint is deliberate: the current AIS live state is process-local, so horizontal scaling would create inconsistent snapshots and duplicate provider connections. Historical/persistent AIS can later be added to PostgreSQL without changing the public API contract.

## Region

The default is `southamerica-east1` (São Paulo) to minimize latency for the current private user. Change it before first creation if another region is required; moving stateful resources later is more disruptive.

## Secrets and Terraform state

`api_token`, `db_password` and `aisstream_api_key` are sensitive Terraform variables and are written to Secret Manager. Terraform state therefore contains sensitive material even though CLI output marks it sensitive.

Never commit `.tfstate`, `.tfvars` or secret files. Use a private, versioned GCS backend with public-access prevention. `backend.tf` intentionally leaves the bucket name unset so the state bucket can be created once before `terraform init`.

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

Infrastructure must not be applied until the repository-wide release gate passes. The gate includes the entire Python test suite, security scans, PostgreSQL/PostGIS integration, strict production startup, browser dashboard smoke, Docker build and Terraform validation.

## First deployment sequence

1. Create or select a dedicated GCP project and attach billing.
2. Create a private/versioned GCS Terraform-state bucket and authenticate Terraform using Application Default Credentials or an authorized CI identity.
3. Build the current Git commit into Artifact Registry and use an immutable image tag/digest for `container_image`.
4. Run `terraform init` with the GCS backend bucket and `terraform plan`.
5. Review the plan and expected recurring costs. Only then run `terraform apply`.
6. Confirm Cloud SQL initializes PostGIS, run the scheduler job once manually, verify `/health`, login, `/v2/runtime/readiness`, `/v2/source-health`, the map layers and a complete browser smoke.
7. Set the two non-secret GitHub repository variables from Terraform outputs (`GCP_WIF_PROVIDER` and `GCP_DEPLOY_SERVICE_ACCOUNT`) plus `GCP_PROJECT_ID` and `GCP_REGION`. GitHub can then publish future images without stored Google service-account keys.

No resource in this directory is created merely by committing these files. Applying Terraform can create billable resources, especially Cloud SQL and continuous AIS compute.
