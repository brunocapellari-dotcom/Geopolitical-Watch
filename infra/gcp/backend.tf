terraform {
  # Supply bucket and prefix at `terraform init` time. The state contains sensitive
  # values and must never live in the repository or an unprotected local file.
  backend "gcs" {}
}
