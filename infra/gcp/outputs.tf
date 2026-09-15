output "web_url" {
  description = "Cloud Run URL for the private site. The URL is network-reachable but application-authenticated."
  value       = google_cloud_run_v2_service.web.uri
}

output "cloud_sql_connection_name" {
  value = google_sql_database_instance.main.connection_name
}

output "raw_bucket" {
  value = google_storage_bucket.raw.name
}

output "artifact_repository" {
  value = google_artifact_registry_repository.geowatch.name
}

output "scheduler_job_name" {
  value = google_cloud_scheduler_job.source_tick.name
}

output "github_workload_identity_provider" {
  description = "Set this as the GitHub repository variable GCP_WIF_PROVIDER."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "github_deployer_service_account" {
  description = "Set this as the GitHub repository variable GCP_DEPLOY_SERVICE_ACCOUNT."
  value       = google_service_account.github_deployer.email
}
