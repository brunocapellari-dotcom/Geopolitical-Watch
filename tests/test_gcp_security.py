from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_TF = ROOT / "infra" / "gcp" / "main.tf"


class GcpSecurityArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main_tf = MAIN_TF.read_text(encoding="utf-8")

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


if __name__ == "__main__":
    unittest.main()
