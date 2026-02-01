"""Tests for ASGI middleware"""

import json
import os
import tempfile
import unittest

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from devhost_cli.middleware import DevhostMiddleware


class MiddlewareTests(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.default_config_path = os.getenv("DEVHOST_CONFIG", "")

    def tearDown(self):
        """Clean up test environment"""
        if self.default_config_path:
            os.environ["DEVHOST_CONFIG"] = self.default_config_path
        elif "DEVHOST_CONFIG" in os.environ:
            del os.environ["DEVHOST_CONFIG"]

    def _write_config(self, data: dict) -> str:
        """Write a temporary config file"""
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        return path

    def test_middleware_adds_devhost_to_scope(self):
        """Test that middleware adds devhost info to scope"""
        path = self._write_config({"hello": 3000})
        os.environ["DEVHOST_CONFIG"] = path

        try:
            app = FastAPI()
            app.add_middleware(DevhostMiddleware)

            @app.get("/test")
            async def test_endpoint(request: Request):
                return {
                    "subdomain": request.scope.get("devhost", {}).get("subdomain"),
                    "target": request.scope.get("devhost", {}).get("target"),
                }

            client = TestClient(app)

            # Test with subdomain
            response = client.get("/test", headers={"host": "hello.localhost"})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["subdomain"], "hello")
            self.assertIsNotNone(data["target"])
            self.assertEqual(data["target"]["port"], 3000)
            self.assertEqual(data["target"]["host"], "127.0.0.1")

            # Test without subdomain
            response = client.get("/test", headers={"host": "localhost"})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIsNone(data["subdomain"])
            self.assertIsNone(data["target"])

        finally:
            os.unlink(path)

    def test_middleware_with_unknown_subdomain(self):
        """Test middleware with unknown subdomain"""
        path = self._write_config({"hello": 3000})
        os.environ["DEVHOST_CONFIG"] = path

        try:
            app = FastAPI()
            app.add_middleware(DevhostMiddleware)

            @app.get("/test")
            async def test_endpoint(request: Request):
                return {"subdomain": request.scope.get("devhost", {}).get("subdomain")}

            client = TestClient(app)
            response = client.get("/test", headers={"host": "unknown.localhost"})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["subdomain"], "unknown")

        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
