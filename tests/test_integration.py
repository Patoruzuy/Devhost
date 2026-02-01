"""Integration tests for router and CLI"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Try to import httpx for router tests
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


@unittest.skipUnless(HTTPX_AVAILABLE, "httpx not installed - router tests require: pip install httpx")
class TestRouterIntegration(unittest.TestCase):
    """Integration tests that start the actual router process"""

    @classmethod
    def setUpClass(cls):
        """Start router subprocess once for all tests"""
        cls.script_dir = Path(__file__).parent.parent.resolve()
        cls.router_dir = cls.script_dir / "router"

        # Create temp config for isolated testing
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_config = Path(cls.temp_dir) / "devhost.json"
        cls.test_domain_file = Path(cls.temp_dir) / "domain"

        # Write test config
        test_routes = {"hello": 8000, "api": "127.0.0.1:8001", "remote": "192.168.1.100:8080"}
        cls.test_config.write_text(json.dumps(test_routes, indent=2), encoding="utf-8")
        cls.test_domain_file.write_text("localhost", encoding="utf-8")

        # Find Python executable
        python_exe = sys.executable

        # Set environment for router
        env = os.environ.copy()
        env["DEVHOST_CONFIG"] = str(cls.test_config)
        env["DEVHOST_DOMAIN"] = "localhost"
        env["PYTHONUNBUFFERED"] = "1"

        # Start router subprocess
        cls.router_process = subprocess.Popen(
            [python_exe, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "5556"],
            cwd=str(cls.router_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for router to be ready
        max_retries = 30
        for _ in range(max_retries):
            try:
                response = httpx.get("http://127.0.0.1:5556/health", timeout=1.0)
                if response.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                time.sleep(0.1)
        else:
            cls.tearDownClass()
            raise RuntimeError("Router failed to start within 3 seconds")

    @classmethod
    def tearDownClass(cls):
        """Stop router subprocess"""
        if hasattr(cls, "router_process"):
            cls.router_process.terminate()
            try:
                cls.router_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.router_process.kill()
                cls.router_process.wait()

        # Cleanup temp files
        if hasattr(cls, "test_config") and cls.test_config.exists():
            cls.test_config.unlink()
        if hasattr(cls, "test_domain_file") and cls.test_domain_file.exists():
            cls.test_domain_file.unlink()
        if hasattr(cls, "temp_dir"):
            Path(cls.temp_dir).rmdir()

    def test_health_endpoint(self):
        """Test /health returns 200"""
        response = httpx.get("http://127.0.0.1:5556/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")

    def test_routes_endpoint(self):
        """Test /routes lists configured routes"""
        response = httpx.get("http://127.0.0.1:5556/routes")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Routes are nested under "routes" key
        routes = data.get("routes", data)
        self.assertIn("hello", routes)
        self.assertIn("api", routes)
        self.assertIn("remote", routes)

    def test_missing_host_header(self):
        """Test request without Host header returns 400"""
        response = httpx.get("http://127.0.0.1:5556/")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("request_id", data)
        self.assertTrue(len(data["request_id"]) > 0)

    def test_unknown_subdomain_404(self):
        """Test request to unknown subdomain returns 404"""
        response = httpx.get("http://127.0.0.1:5556/", headers={"Host": "unknown.localhost"})
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("No route found", data["error"])
        self.assertIn("request_id", data)

    def test_request_id_in_headers(self):
        """Test X-Request-ID header is present in responses"""
        response = httpx.get("http://127.0.0.1:5556/health")
        self.assertIn("x-request-id", response.headers)
        request_id = response.headers["x-request-id"]
        self.assertTrue(len(request_id) > 0)


class TestCLIIntegration(unittest.TestCase):
    """Integration tests for CLI commands"""

    @classmethod
    def setUpClass(cls):
        """Setup temp config for CLI tests"""
        cls.script_dir = Path(__file__).parent.parent.resolve()
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_config = Path(cls.temp_dir) / "devhost.json"
        cls.test_domain_dir = Path(cls.temp_dir) / ".devhost"
        cls.test_domain_dir.mkdir()
        cls.test_domain_file = cls.test_domain_dir / "domain"

        # Write empty config
        cls.test_config.write_text("{}", encoding="utf-8")
        cls.test_domain_file.write_text("localhost", encoding="utf-8")

        # Set environment - point to temp directory as "script dir"
        cls.env = os.environ.copy()
        cls.env["DEVHOST_CONFIG"] = str(cls.test_config)
        # Make CLI find .devhost/domain in our temp dir
        cls.env["HOME"] = str(cls.temp_dir)
        cls.env["USERPROFILE"] = str(cls.temp_dir)

        cls.python_exe = sys.executable
        cls.devhost_script = cls.script_dir / "devhost"

    @classmethod
    def tearDownClass(cls):
        """Cleanup temp files"""
        if cls.test_config.exists():
            cls.test_config.unlink()
        if cls.test_domain_file.exists():
            cls.test_domain_file.unlink()
        if cls.test_domain_dir.exists():
            cls.test_domain_dir.rmdir()
        Path(cls.temp_dir).rmdir()

    def _run_devhost(self, *args):
        """Run devhost CLI command"""
        cmd = [self.python_exe, str(self.devhost_script)] + list(args)
        result = subprocess.run(cmd, env=self.env, capture_output=True, text=True)
        return result

    def test_add_and_list(self):
        """Test adding a route and listing it"""
        # Add route
        result = self._run_devhost("add", "test", "9000")
        self.assertEqual(result.returncode, 0)

        # List routes
        result = self._run_devhost("list")
        self.assertEqual(result.returncode, 0)
        self.assertIn("test", result.stdout)
        self.assertIn("9000", result.stdout)

    def test_add_remote_ip(self):
        """Test adding a route with remote IP"""
        result = self._run_devhost("add", "remote", "192.168.1.50:8080")
        # Print debug info if test fails
        if result.returncode != 0:
            print(f"STDERR: {result.stderr}")
            print(f"STDOUT: {result.stdout}")
        self.assertEqual(result.returncode, 0)

        # Verify in config
        config = json.loads(self.test_config.read_text(encoding="utf-8"))
        self.assertIn("remote", config)
        self.assertEqual(config["remote"], "192.168.1.50:8080")

    def test_remove_route(self):
        """Test removing a route"""
        # Add then remove
        self._run_devhost("add", "temp", "7000")
        result = self._run_devhost("remove", "temp")
        self.assertEqual(result.returncode, 0)

        # Verify removed
        config = json.loads(self.test_config.read_text(encoding="utf-8"))
        self.assertNotIn("temp", config)

    def test_validate_command(self):
        """Test validate command"""
        # Add valid route
        self._run_devhost("add", "valid", "8888")

        result = self._run_devhost("validate")
        self.assertEqual(result.returncode, 0)
        # validate command output includes status messages
        self.assertIn("Config file", result.stdout)


if __name__ == "__main__":
    unittest.main()
