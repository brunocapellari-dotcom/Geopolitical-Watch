terraform {
  # The state bucket is supplied at `terraform init` time so the same code can be
  # validated without touching GCP. Production state must live in a dedicated,
  # versioned, private GCS bucket and never become canonical in Replit/Claude/local.
  backend "gcs" {
    prefix = "geowatch/terraform/state"
  }
}
