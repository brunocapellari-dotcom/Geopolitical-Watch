variable "project_id" {
  description = "Google Cloud project ID dedicated to Geopolitical-Watch."
  type        = string
}

variable "region" {
  description = "Primary region. Sao Paulo is the default for the current private user."
  type        = string
  default     = "southamerica-east1"
}

variable "container_image" {
  description = "Immutable container image URI, preferably pinned by digest."
  type        = string
}

variable "api_token" {
  description = "Private site secret. Minimum 32 characters. Never commit a tfvars file containing this value."
  type        = string
  sensitive   = true
  validation {
    condition     = length(var.api_token) >= 32
    error_message = "api_token must contain at least 32 characters."
  }
}

variable "db_password" {
  description = "Cloud SQL geowatch user password. Never commit a tfvars file containing this value."
  type        = string
  sensitive   = true
  validation {
    condition     = length(var.db_password) >= 24
    error_message = "db_password must contain at least 24 characters."
  }
}

variable "aisstream_api_key" {
  description = "AISStream key. Leave empty to deploy the site without continuous AIS."
  type        = string
  sensitive   = true
  default     = ""
}

variable "enable_continuous_ais" {
  description = "Keeps one Cloud Run instance warm with non-throttled CPU for the AIS websocket. This creates continuous compute cost."
  type        = bool
  default     = false
}

variable "database_tier" {
  description = "Cloud SQL machine tier. Keep cost explicit rather than silently up-sizing."
  type        = string
  default     = "db-g1-small"
}

variable "database_high_availability" {
  description = "Use regional Cloud SQL HA. Increases cost materially."
  type        = bool
  default     = false
}

variable "scheduler_cron" {
  description = "Cloud Scheduler cadence. The internal registry decides which sources are actually due."
  type        = string
  default     = "*/5 * * * *"
}

variable "github_repository" {
  description = "Repository allowed to federate to the deploy service account."
  type        = string
  default     = "brunocapellari-dotcom/Geopolitical-Watch"
}
