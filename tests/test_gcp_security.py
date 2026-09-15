from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_TF = ROOT / "infra" / "gcp" / "main.tf"
VERSIONS_TF = ROOT / "infra" / "gcp" / "versions.tf"


class GcpSecurityArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main_tf = MAIN_TF.read_text(encoding="utf-8")
        cls.versions_tf = VERSIONS_TF.read_text(encoding="utf-8")

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


if __name__ == "__main__":
    unittest.main()
