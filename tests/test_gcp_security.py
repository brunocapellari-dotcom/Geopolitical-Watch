from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_TF = ROOT / "infra" / "gcp" / "main.tf"
VERSIONS_TF = ROOT / "infra" / "gcp" / "versions.tf"
BACKEND_TF = ROOT / "infra" / "gcp" / "backend.tf"
VARIABLES_TF = ROOT / "infra" / "gcp" / "variables.tf"
RELEASE_YML = ROOT / ".github" / "workflows" / "gcp-release.yml"
RAW_STORE_PY = ROOT / "geowatch" / "raw_store.py"


class GcpSecurityArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main_tf = MAIN_TF.read_text(encoding="utf-8")
        cls.versions_tf = VERSIONS_TF.read_text(encoding="utf-8")
        cls.backend_tf = BACKEND_TF.read_text(encoding="utf-8")
        cls.variables_tf = VARIABLES_TF.read_text(encoding="utf-8")
        cls.release_yml = RELEASE_YML.read_text(encoding="utf-8")
        cls.raw_store_py = RAW_STORE_PY.read_text(encoding="utf-8")

    def test_cloud_sql_has_no_public_ipv4_and_requires_encryption(self) -> None:
        self.assertIn('ipv4_enabled                                  = false', self.main_tf)
        self.assertIn('private_network                               = google_compute_network.runtime.id', self.main_tf)
        self.assertIn('ssl_mode                                      = "ENCRYPTED_ONLY"', self.main_tf)
        self.assertNotIn('ipv4_enabled = true', self.main_tf)

    def test_private_services_access_is_explicit(self) -> None:
        self.assertIn('resource "google_compute_network" "runtime"', self.main_tf)
        self.assertIn('resource "google_compute_global_address" "private_services"', self.main_tf)
        self.assertIn('resource "google_service_networking_connection" "private_services"', self.main_tf)
        self.assertIn('"servicenetworking.googleapis.com"', self.main_tf)

    def test_web_and_job_use_direct_vpc_egress(self) -> None:
        self.assertGreaterEqual(self.main_tf.count('egress = "PRIVATE_RANGES_ONLY"'), 2)
        self.assertGreaterEqual(self.main_tf.count('network    = google_compute_network.runtime.name'), 2)
        self.assertGreaterEqual(self.main_tf.count('subnetwork = google_compute_subnetwork.runtime.name'), 2)

    def test_raw_bucket_runtime_iam_is_append_only(self) -> None:
        self.assertIn('resource "google_storage_bucket_iam_member" "runtime_raw_create"', self.main_tf)
        self.assertIn('role   = "roles/storage.objectCreator"', self.main_tf)
        self.assertIn('resource "google_storage_bucket_iam_member" "runtime_raw_read"', self.main_tf)
        self.assertIn('role   = "roles/storage.objectViewer"', self.main_tf)
        self.assertNotIn('roles/storage.objectAdmin', self.main_tf)
        self.assertNotIn('roles/storage.objectUser', self.main_tf)

    def test_gcs_raw_writes_require_object_absence(self) -> None:
        self.assertGreaterEqual(self.raw_store_py.count('if_generation_match=0'), 2)
        self.assertIn('if not blob.exists(self.client):', self.raw_store_py)
        self.assertIn('if not observation.exists(self.client):', self.raw_store_py)

    def test_terraform_state_does_not_receive_secret_payload_fields(self) -> None:
        self.assertIn('secret_data_wo         = var.api_token', self.main_tf)
        self.assertIn('secret_data_wo         = var.db_password', self.main_tf)
        self.assertIn('secret_data_wo         = var.aisstream_api_key', self.main_tf)
        self.assertIn('password_wo         = var.db_password', self.main_tf)
        self.assertNotIn('secret_data = var.api_token', self.main_tf)
        self.assertNotIn('secret_data = var.db_password', self.main_tf)
        self.assertNotIn('secret_data = var.aisstream_api_key', self.main_tf)
        self.assertNotIn('password = var.db_password', self.main_tf)

    def test_terraform_requires_write_only_attribute_support(self) -> None:
        self.assertIn('required_version = ">= 1.11.0, < 2.0.0"', self.versions_tf)
        self.assertIn('version = "= 7.46.1"', self.versions_tf)

    def test_terraform_uses_single_canonical_remote_state_backend(self) -> None:
        self.assertIn('backend "gcs"', self.backend_tf)
        self.assertIn('prefix = "geowatch/terraform/state"', self.backend_tf)
        self.assertNotIn('backend "gcs"', self.versions_tf)

    def test_foundation_can_be_created_before_first_runtime_image(self) -> None:
        self.assertIn('variable "deploy_runtime"', self.variables_tf)
        self.assertIn('default     = false', self.variables_tf)
        self.assertGreaterEqual(self.main_tf.count('count               = var.deploy_runtime ? 1 : 0'), 2)
        self.assertIn('container_image must be an immutable scanned image when deploy_runtime=true.', self.main_tf)

    def test_single_release_workflow_supports_bootstrap_publish_and_runtime_deploy(self) -> None:
        self.assertIn("inputs.confirm == 'PUBLISH'", self.release_yml)
        self.assertIn("inputs.confirm == 'DEPLOY'", self.release_yml)
        self.assertIn('No Cloud Run runtime was changed by this workflow.', self.release_yml)
        self.assertNotIn('gcloud run deploy', self.release_yml)

    def test_release_only_changes_runtime_image_after_terraform_provisions_runtime(self) -> None:
        self.assertIn('ignore_changes = [template[0].containers[0].image]', self.main_tf)
        self.assertIn('ignore_changes = [template[0].template[0].containers[0].image]', self.main_tf)
        self.assertIn('gcloud run services update', self.release_yml)
        self.assertIn('gcloud run jobs update', self.release_yml)


if __name__ == "__main__":
    unittest.main()
