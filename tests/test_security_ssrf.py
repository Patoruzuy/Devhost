"""Test SSRF protection in router proxy"""

import json
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from router.app import app


class DummyResponse:
    def __init__(self, status_code=200, content=b"ok"):
        self.content = content
        self.status_code = status_code
        self.headers = {"content-type": "text/plain"}

    async def aiter_bytes(self, chunk_size=None):
        yield self.content

    async def aclose(self):
        pass


class DummyAsyncClient:
    def __init__(self, *args, **kwargs):
        self.captured_request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, **kwargs):
        self.captured_request = {"method": method, "url": url, "kwargs": kwargs}
        return DummyResponse()

    async def aclose(self):
        pass


class DummySendClient:
    def __init__(self):
        self.captured_request: dict | None = None

    def build_request(self, method, url, **kwargs):
        self.captured_request = {"method": method, "url": url, "kwargs": kwargs}
        return self.captured_request

    async def send(self, request, **kwargs):
        return DummyResponse()


class TestSSRFProtection(unittest.TestCase):
    """Test SSRF protection for router proxy"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "devhost.json"
        self.config_path.write_text(json.dumps({"api": 8000, "test": 9000}))
        os.environ["DEVHOST_CONFIG"] = str(self.config_path)
        os.environ["DEVHOST_DOMAIN"] = "localhost"
        os.environ.pop("DEVHOST_ALLOW_PRIVATE_NETWORKS", None)
        self.client = TestClient(app)

    def tearDown(self):
        os.environ.pop("DEVHOST_CONFIG", None)
        os.environ.pop("DEVHOST_DOMAIN", None)
        os.environ.pop("DEVHOST_ALLOW_PRIVATE_NETWORKS", None)
        if Path(self.config_path).exists():
            Path(self.config_path).unlink()

    def test_block_aws_metadata_endpoint(self):
        """Block AWS EC2 metadata endpoint 169.254.169.254:80"""
        self.config_path.write_text(json.dumps({"api": "169.254.169.254:80"}))
        response = self.client.get("/test", headers={"Host": "api.localhost"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("SSRF", response.text.upper())

    def test_block_gcp_metadata_endpoint(self):
        """Block GCP metadata.google.internal"""
        self.config_path.write_text(json.dumps({"api": "metadata.google.internal:80"}))
        response = self.client.get("/test", headers={"Host": "api.localhost"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("SSRF", response.text.upper())

    def test_block_private_network_10(self):
        """Block 10.0.0.0/8 private network"""
        self.config_path.write_text(json.dumps({"api": "10.0.0.1:8080"}))
        response = self.client.get("/test", headers={"Host": "api.localhost"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("private", response.text.lower())

    def test_block_private_network_192(self):
        """Block 192.168.0.0/16 private network"""
        self.config_path.write_text(json.dumps({"api": "192.168.1.100:3000"}))
        response = self.client.get("/test", headers={"Host": "api.localhost"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("private", response.text.lower())

    def test_block_private_network_172(self):
        """Block 172.16.0.0/12 private network"""
        self.config_path.write_text(json.dumps({"api": "172.17.0.2:8000"}))
        response = self.client.get("/test", headers={"Host": "api.localhost"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("private", response.text.lower())

    def test_allow_localhost(self):
        """Allow 127.0.0.1:8000 (should 502/200 not 403)"""
        self.config_path.write_text(json.dumps({"api": "127.0.0.1:8000"}))
        with patch("router.app.http_client", new=DummySendClient()):
            response = self.client.get("/test", headers={"Host": "api.localhost"})
        # Should not be SSRF blocked (403)
        self.assertNotEqual(response.status_code, 403)

    def test_allow_localhost_string(self):
        """Allow localhost:9000"""
        self.config_path.write_text(json.dumps({"api": "localhost:9000"}))
        with patch("router.app.http_client", new=DummySendClient()):
            response = self.client.get("/test", headers={"Host": "api.localhost"})
        self.assertNotEqual(response.status_code, 403)

    def test_allow_ipv6_loopback(self):
        """Allow [::1]:8000 IPv6 loopback"""
        self.config_path.write_text(json.dumps({"api": "[::1]:8000"}))
        with patch("router.app.http_client", new=DummySendClient()):
            response = self.client.get("/test", headers={"Host": "api.localhost"})
        self.assertNotEqual(response.status_code, 403)

    def test_block_link_local_ipv4(self):
        """Block 169.254.0.0/16 link-local addresses"""
        self.config_path.write_text(json.dumps({"api": "169.254.1.1:80"}))
        response = self.client.get("/test", headers={"Host": "api.localhost"})
        self.assertEqual(response.status_code, 403)

    def test_websocket_ssrf_protection(self):
        """WebSocket upgrade must also block SSRF targets"""
        self.config_path.write_text(json.dumps({"api": "10.0.0.1:8080"}))
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("/ws/test", headers={"Host": "api.localhost"}):
                pass

    def test_opt_in_private_networks(self):
        """Allow private networks when DEVHOST_ALLOW_PRIVATE_NETWORKS=1"""
        os.environ["DEVHOST_ALLOW_PRIVATE_NETWORKS"] = "1"
        self.config_path.write_text(json.dumps({"api": "192.168.1.100:3000"}))
        with patch("router.app.http_client", new=DummySendClient()):
            response = self.client.get("/test", headers={"Host": "api.localhost"})
            # Should not be 403 when opt-in enabled
            self.assertNotEqual(response.status_code, 403)

    def test_invalid_hostname_resolution(self):
        """Block unresolvable hostnames that could resolve to private IPs"""
        self.config_path.write_text(json.dumps({"api": "internal.corp:8000"}))
        response = self.client.get("/test", headers={"Host": "api.localhost"})
        # Should fail with 502 or 403, not proceed
        self.assertIn(response.status_code, [403, 502, 503])

    def test_request_id_in_blocked_response(self):
        """Blocked SSRF attempts must include request ID for auditing"""
        self.config_path.write_text(json.dumps({"api": "169.254.169.254:80"}))
        response = self.client.get("/test", headers={"Host": "api.localhost"})
        self.assertEqual(response.status_code, 403)
        # Check for request ID pattern (UUID or similar)
        self.assertIn("request", response.text.lower())

    def test_logging_of_blocked_attempts(self):
        """SSRF blocks must be logged at WARNING level"""
        self.config_path.write_text(json.dumps({"api": "169.254.169.254:80"}))
        with self.assertLogs("devhost.router", level=logging.WARNING) as log:
            self.client.get("/test", headers={"Host": "api.localhost"})
            # Check that SSRF block was logged
            self.assertTrue(
                any("169.254.169.254" in msg or "SSRF" in msg or "blocked" in msg.lower() for msg in log.output)
            )

    def test_block_docker_network(self):
        """Block Docker bridge network 172.16.0.0/12"""
        self.config_path.write_text(json.dumps({"api": "172.18.0.2:8000"}))
        response = self.client.get("/test", headers={"Host": "api.localhost"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("private", response.text.lower())


if __name__ == "__main__":
    unittest.main()
