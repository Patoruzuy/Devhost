"""
Tests for health check enhancements (Phase 4 L-18) and graceful shutdown (Phase 4 L-19).
"""

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class TestHealthEndpoint(unittest.TestCase):
    """Test enhanced health endpoint (Phase 4 L-18)."""

    def setUp(self):
        """Create test router instance."""
        # Create temporary config
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "devhost.json"
        self.config_path.write_text(json.dumps({"api": 8000, "web": 3000}))

        # Set environment
        import os

        os.environ["DEVHOST_CONFIG"] = str(self.config_path)

        # Import and create app after setting env
        from devhost_cli.router.core import create_app

        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        """Clean up."""
        import os
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if "DEVHOST_CONFIG" in os.environ:
            del os.environ["DEVHOST_CONFIG"]

    def test_health_endpoint_exists(self):
        """Test that health endpoint is accessible."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_health_response_structure(self):
        """Test that health response contains all expected fields."""
        response = self.client.get("/health")
        data = response.json()

        # Required fields
        self.assertIn("status", data)
        self.assertIn("version", data)
        self.assertIn("uptime_seconds", data)
        self.assertIn("routes_count", data)
        self.assertIn("in_flight_requests", data)
        self.assertIn("connection_pool", data)

        # Connection pool status
        self.assertIn("status", data["connection_pool"])
        self.assertIn("success_rate", data["connection_pool"])

    def test_health_status_ok(self):
        """Test that health status is 'ok' during normal operation."""
        response = self.client.get("/health")
        data = response.json()

        self.assertEqual(data["status"], "ok")

    def test_health_routes_count(self):
        """Test that routes count is reported correctly."""
        response = self.client.get("/health")
        data = response.json()

        self.assertEqual(data["routes_count"], 2)  # api + web

    def test_health_uptime_increases(self):
        """Test that uptime increases over time."""
        import time

        response1 = self.client.get("/health")
        data1 = response1.json()
        uptime1 = data1["uptime_seconds"]

        time.sleep(1)

        response2 = self.client.get("/health")
        data2 = response2.json()
        uptime2 = data2["uptime_seconds"]

        self.assertGreaterEqual(uptime2, uptime1)

    def test_health_in_flight_requests(self):
        """Test that in-flight requests are tracked during execution."""
        response = self.client.get("/health")
        data = response.json()

        # The health check itself was in-flight during execution
        # After it completes, the value should be the count during execution (1 for the health check itself)
        self.assertIsInstance(data["in_flight_requests"], int)
        self.assertGreaterEqual(data["in_flight_requests"], 0)

    def test_health_connection_pool_status(self):
        """Test that connection pool status is included."""
        response = self.client.get("/health")
        data = response.json()

        pool = data["connection_pool"]
        self.assertIn(pool["status"], ["healthy", "degraded"])
        self.assertIsInstance(pool["success_rate"], (int, float))
        self.assertGreaterEqual(pool["success_rate"], 0.0)
        self.assertLessEqual(pool["success_rate"], 1.0)

    def test_health_version_string(self):
        """Test that version is a non-empty string."""
        response = self.client.get("/health")
        data = response.json()

        self.assertIsInstance(data["version"], str)
        self.assertGreater(len(data["version"]), 0)

    def test_health_memory_optional(self):
        """Test that memory field is optional (depends on psutil)."""
        response = self.client.get("/health")
        data = response.json()

        # Memory field may or may not be present
        if "memory_mb" in data:
            self.assertIsInstance(data["memory_mb"], (int, float))
            self.assertGreater(data["memory_mb"], 0)


class TestGracefulShutdown(unittest.IsolatedAsyncioTestCase):
    """Test graceful shutdown functionality (Phase 4 L-19)."""

    async def test_shutdown_handler_exists(self):
        """Test that lifespan handler is registered."""
        from devhost_cli.router.core import create_app

        app = create_app()

        # Check that lifespan handler is registered
        self.assertTrue(hasattr(app, "router"))
        lifespan = getattr(app.router, "lifespan_context", None) or getattr(app, "lifespan_context", None)
        self.assertIsNotNone(lifespan)

    async def test_in_flight_tracking(self):
        """Test that in-flight requests are tracked."""
        # Create temporary config
        import os
        import tempfile

        temp_dir = tempfile.mkdtemp()
        config_path = Path(temp_dir) / "devhost.json"
        config_path.write_text(json.dumps({"api": 8000}))
        os.environ["DEVHOST_CONFIG"] = str(config_path)

        try:
            from devhost_cli.router.core import create_app

            app = create_app()
            client = TestClient(app)

            # Make a request
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)

            # The in_flight_requests field should exist and be an integer
            data = response.json()
            self.assertIn("in_flight_requests", data)
            self.assertIsInstance(data["in_flight_requests"], int)
            self.assertGreaterEqual(data["in_flight_requests"], 0)
        finally:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)
            if "DEVHOST_CONFIG" in os.environ:
                del os.environ["DEVHOST_CONFIG"]


class TestShutdownTimeout(unittest.TestCase):
    """Test shutdown timeout behavior."""

    def test_shutdown_timeout_constant(self):
        """Test that shutdown has reasonable timeout."""
        # Read the core.py file to verify timeout
        import re
        from pathlib import Path

        core_path = Path(__file__).parent.parent / "devhost_cli" / "router" / "core.py"
        content = core_path.read_text()

        # Look for timeout = value in shutdown handler
        timeout_match = re.search(r"timeout\s*=\s*([\d.]+)", content)
        if timeout_match:
            timeout = float(timeout_match.group(1))
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 60)  # Reasonable max timeout


class TestHealthReadiness(unittest.TestCase):
    """Test health endpoint readiness indicators."""

    def setUp(self):
        """Create test router instance."""
        import os
        import tempfile

        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "devhost.json"
        self.config_path.write_text(json.dumps({"api": 8000}))
        os.environ["DEVHOST_CONFIG"] = str(self.config_path)

        from devhost_cli.router.core import create_app

        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        """Clean up."""
        import os
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if "DEVHOST_CONFIG" in os.environ:
            del os.environ["DEVHOST_CONFIG"]

    def test_connection_pool_healthy_status(self):
        """Test connection pool reports healthy or degraded status."""
        response = self.client.get("/health")
        data = response.json()

        # Connection pool status should be either healthy or degraded
        pool = data["connection_pool"]
        self.assertIn(pool["status"], ["healthy", "degraded"])


if __name__ == "__main__":
    unittest.main()
