"""Tests for router metrics module"""

import time
import unittest

from devhost_cli.router.metrics import Metrics


class MetricsTests(unittest.TestCase):
    def test_metrics_initialization(self):
        """Test metrics are initialized to zero"""
        metrics = Metrics()
        self.assertEqual(metrics.requests_total, 0)
        self.assertEqual(metrics.requests_by_status, {})
        self.assertEqual(metrics.requests_by_subdomain, {})

    def test_record_increments_total(self):
        """Test that record increments total requests"""
        metrics = Metrics()
        metrics.record("hello", 200)
        self.assertEqual(metrics.requests_total, 1)

    def test_record_tracks_status_codes(self):
        """Test that status codes are tracked"""
        metrics = Metrics()
        metrics.record("hello", 200)
        metrics.record("api", 200)
        metrics.record("error", 404)

        self.assertEqual(metrics.requests_by_status[200], 2)
        self.assertEqual(metrics.requests_by_status[404], 1)

    def test_record_tracks_subdomain_stats(self):
        """Test subdomain statistics tracking"""
        metrics = Metrics()
        metrics.record("hello", 200)
        metrics.record("hello", 200)
        metrics.record("hello", 404)

        subdomain_stats = metrics.requests_by_subdomain["hello"]
        self.assertEqual(subdomain_stats["count"], 3)
        self.assertEqual(subdomain_stats["errors"], 1)

    def test_record_ignores_none_subdomain(self):
        """Test that None subdomain is not tracked"""
        metrics = Metrics()
        metrics.record(None, 200)

        self.assertEqual(metrics.requests_total, 1)
        self.assertEqual(metrics.requests_by_subdomain, {})

    def test_record_multiple_subdomains(self):
        """Test tracking multiple subdomains"""
        metrics = Metrics()
        metrics.record("api", 200)
        metrics.record("web", 200)
        metrics.record("api", 500)

        self.assertEqual(len(metrics.requests_by_subdomain), 2)
        self.assertEqual(metrics.requests_by_subdomain["api"]["count"], 2)
        self.assertEqual(metrics.requests_by_subdomain["api"]["errors"], 1)
        self.assertEqual(metrics.requests_by_subdomain["web"]["count"], 1)
        self.assertEqual(metrics.requests_by_subdomain["web"]["errors"], 0)

    def test_snapshot_includes_uptime(self):
        """Test that snapshot includes uptime"""
        metrics = Metrics()
        time.sleep(0.1)

        snapshot = metrics.snapshot()
        self.assertIn("uptime_seconds", snapshot)
        self.assertGreaterEqual(snapshot["uptime_seconds"], 0)

    def test_snapshot_includes_all_metrics(self):
        """Test snapshot contains all metric categories"""
        metrics = Metrics()
        metrics.record("hello", 200)

        snapshot = metrics.snapshot()
        self.assertIn("uptime_seconds", snapshot)
        self.assertIn("requests_total", snapshot)
        self.assertIn("requests_by_status", snapshot)
        self.assertIn("requests_by_subdomain", snapshot)

    def test_snapshot_is_copy(self):
        """Test that snapshot returns independent data"""
        metrics = Metrics()
        metrics.record("hello", 200)

        snapshot1 = metrics.snapshot()
        metrics.record("api", 200)
        snapshot2 = metrics.snapshot()

        self.assertNotEqual(snapshot1["requests_total"], snapshot2["requests_total"])


if __name__ == "__main__":
    unittest.main()
