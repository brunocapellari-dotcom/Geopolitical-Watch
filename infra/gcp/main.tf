locals {
  service_name      = "geowatch-monitor"
  scheduler_job     = "geowatch-source-tick"
  artifact_repo     = "geowatch"
  database_name     = "geowatch"
  database_user     = "geowatch"
  raw_bucket_prefix = "${var.project_id}-geowatch-raw"

  required_apis = toset([
    "artifactregistry.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "sts.googleapis.com",
    "storage.googleapis.com",
  ])
}

resource "google_project_service" "required" {
  for_each           = local.required_apis
  service            = each.value
  disable_on_destroy = false
}

resource "random_id" "raw_bucket" {
  byte_length = 4
}

resource "google_artifact_registry_repository" "geowatch" {
  location      = var.region
  repository_id = local.artifact_repo
  format        = "DOCKER"
  description   = "Geopolitical-Watch production images"
  depends_on    = [google_project_service.required]
}

resource "google_storage_bucket" "raw" {
  name                        = "${local.raw_bucket_prefix}-${random_id.raw_bucket.hex}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_compute_network" "runtime" {
  name                    = "geowatch-runtime"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.required]
}

resource "google_compute_subnetwork" "runtime" {
  name                     = "geowatch-runtime-${var.region}"
  region                   = var.region
  network                  = google_compute_network.runtime.id
  ip_cidr_range            = var.runtime_subnet_cidr
  private_ip_google_access = true
}

resource "google_compute_global_address" "private_services" {
  name          = "geowatch-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.runtime.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.runtime.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]

  depends_on = [google_project_service.required]
}

resource "google_service_account" "runtime" {
  account_id   = "geowatch-runtime"
  display_name = "Geopolitical-Watch runtime"
}

resource "google_service_account" "scheduler" {
  account_id   = "geowatch-scheduler"
  display_name = "Geopolitical-Watch Cloud Scheduler invoker"
}

resource "google_service_account" "github_deployer" {
  account_id   = "geowatch-github-deployer"
  display_name = "Geopolitical-Watch GitHub deployment identity"
}

resource "google_project_iam_member" "runtime_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_storage_bucket_iam_member" "runtime_raw" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret" "api_token" {
  secret_id = "geowatch-api-token"
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "api_token" {
  secret                 = google_secret_manager_secret.api_token.id
  secret_data_wo         = var.api_token
  secret_data_wo_version = "1"
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = "geowatch-db-password"
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret                 = google_secret_manager_secret.db_password.id
  secret_data_wo         = var.db_password
  secret_data_wo_version = "1"
}

resource "google_secret_manager_secret" "aisstream" {
  secret_id = "geowatch-aisstream-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "aisstream" {
  count                  = length(trimspace(var.aisstream_api_key)) > 0 ? 1 : 0
  secret                 = google_secret_manager_secret.aisstream.id
  secret_data_wo         = var.aisstream_api_key
  secret_data_wo_version = "1"
}

resource "google_sql_database_instance" "main" {
  name                = "geowatch-postgres"
  database_version    = "POSTGRES_18"
  region              = var.region
  deletion_protection = true

  settings {
    tier              = var.database_tier
    availability_type = var.database_high_availability ? "REGIONAL" : "ZONAL"
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "03:00"
    }

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.runtime.id
      enable_private_path_for_google_cloud_services = true
      ssl_mode                                      = "ENCRYPTED_ONLY"
    }
  }

  depends_on = [
    google_project_service.required,
    google_service_networking_connection.private_services,
  ]
}

resource "google_sql_database" "geowatch" {
  name     = local.database_name
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "geowatch" {
  name                = local.database_user
  instance            = google_sql_database_instance.main.name
  password_wo         = var.db_password
  password_wo_version = 1
}

resource "google_cloud_run_v2_service" "web" {
  name                = local.service_name
  location            = var.region
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.runtime.email
    timeout         = "300s"

    scaling {
      min_instance_count = var.enable_continuous_ais ? 1 : 0
      max_instance_count = 1
    }

    vpc_access {
      network_interfaces {
        network    = google_compute_network.runtime.name
        subnetwork = google_compute_subnetwork.runtime.name
      }
      egress = "PRIVATE_RANGES_ONLY"
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.main.connection_name]
      }
    }

    containers {
      image = var.container_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle = var.enable_continuous_ais ? false : true
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      env {
        name  = "GEOWATCH_STRICT_PRODUCTION"
        value = "1"
      }
      env {
        name  = "GEOWATCH_EXTERNAL_SCHEDULER"
        value = "1"
      }
      env {
        name  = "GEOWATCH_SOURCE_SCHEDULER"
        value = "0"
      }
      env {
        name  = "GEOWATCH_EMBEDDED_COLLECTOR"
        value = "0"
      }
      env {
        name  = "GEOWATCH_COOKIE_SECURE"
        value = "1"
      }
      env {
        name  = "GEOWATCH_WPI_RUNTIME"
        value = "1"
      }
      env {
        name  = "GEOWATCH_ALWAYS_ON"
        value = var.enable_continuous_ais ? "1" : "0"
      }
      env {
        name  = "GEOWATCH_RAW_BUCKET"
        value = google_storage_bucket.raw.name
      }
      env {
        name  = "GEOWATCH_DB_USER"
        value = local.database_user
      }
      env {
        name  = "GEOWATCH_DB_NAME"
        value = local.database_name
      }
      env {
        name  = "GEOWATCH_DB_HOST"
        value = "/cloudsql/${google_sql_database_instance.main.connection_name}"
      }

      env {
        name = "GEOWATCH_DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "GEOWATCH_API_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.api_token.secret_id
            version = "latest"
          }
        }
      }

      dynamic "env" {
        for_each = var.enable_continuous_ais && length(trimspace(var.aisstream_api_key)) > 0 ? [1] : []
        content {
          name = "AISSTREAM_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.aisstream.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_project_iam_member.runtime_cloudsql,
    google_project_iam_member.runtime_secret_accessor,
    google_secret_manager_secret_version.api_token,
    google_secret_manager_secret_version.db_password,
    google_sql_database.geowatch,
    google_sql_user.geowatch,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "web_public_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.web.location
  name     = google_cloud_run_v2_service.web.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_job" "source_tick" {
  name                = local.scheduler_job
  location            = var.region
  deletion_protection = true

  template {
    template {
      service_account = google_service_account.runtime.email
      timeout         = "900s"
      max_retries     = 1

      vpc_access {
        network_interfaces {
          network    = google_compute_network.runtime.name
          subnetwork = google_compute_subnetwork.runtime.name
        }
        egress = "PRIVATE_RANGES_ONLY"
      }

      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.main.connection_name]
        }
      }

      containers {
        image   = var.container_image
        command = ["python", "-m", "geowatch"]
        args    = ["scheduler-tick"]

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }

        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }

        env {
          name  = "GEOWATCH_RAW_BUCKET"
          value = google_storage_bucket.raw.name
        }
        env {
          name  = "GEOWATCH_DB_USER"
          value = local.database_user
        }
        env {
          name  = "GEOWATCH_DB_NAME"
          value = local.database_name
        }
        env {
          name  = "GEOWATCH_DB_HOST"
          value = "/cloudsql/${google_sql_database_instance.main.connection_name}"
        }
        env {
          name  = "GEOWATCH_ANALYSIS_CONFIG"
          value = "config/sources.production.json"
        }

        env {
          name = "GEOWATCH_DB_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.db_password.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_project_iam_member.runtime_cloudsql,
    google_project_iam_member.runtime_secret_accessor,
    google_secret_manager_secret_version.db_password,
    google_sql_database.geowatch,
    google_sql_user.geowatch,
  ]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_job.source_tick.location
  name     = google_cloud_run_v2_job.source_tick.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "source_tick" {
  name             = "geowatch-source-schedule"
  description      = "Invoke the registry-driven Geopolitical-Watch source tick"
  schedule         = var.scheduler_cron
  time_zone        = "Etc/UTC"
  region           = var.region
  attempt_deadline = "600s"

  retry_config {
    retry_count          = 2
    min_backoff_duration = "30s"
    max_backoff_duration = "300s"
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.source_tick.name}:run"
    body        = base64encode("{}")
    headers = {
      "Content-Type" = "application/json"
    }
    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [
    google_project_service.required,
    google_cloud_run_v2_job_iam_member.scheduler_invoker,
  ]
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "geowatch-github"
  display_name              = "Geowatch GitHub"
  description               = "Keyless GitHub Actions federation for Geopolitical-Watch"
  depends_on                = [google_project_service.required]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  attribute_condition = "assertion.repository == '${var.github_repository}' && assertion.ref == 'refs/heads/main'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_wif" {
  service_account_id = google_service_account.github_deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

resource "google_project_iam_member" "github_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

resource "google_project_iam_member" "github_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.github_deployer.email}"
}

resource "google_service_account_iam_member" "github_act_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.github_deployer.email}"
}
