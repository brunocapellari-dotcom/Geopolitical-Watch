terraform {
  required_version = ">= 1.11.0, < 2.0.0"

  backend "gcs" {
    prefix = "geowatch/terraform/state"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "= 7.46.1"
    }
    random = {
      source  = "hashicorp/random"
      version = "= 3.9.1"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
