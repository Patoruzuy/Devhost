import json
import logging
import os
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from devhost_cli.router.core import create_app
from devhost_cli.router.utils import extract_subdomain

app = create_app()


class DummyRequest:
    def __init__(self, method, url, headers=None, content=None, timeout=None):
        self.method = method
        self.url = url
        self.headers = headers
        self.content = content
        self.timeout = timeout


class DummyResponse:
    def __init__(self):
        self.content = b"ok"
        self.status_code = 200
        self.headers = {"content-type": "text/plain", "connection": "keep-alive"}

    async def aiter_bytes(self, chunk_size=None):
        """Stream response body in chunks."""
        yield self.content

    async def aclose(self):
        """Close the response."""
        pass


class DummyAsyncClient:
    captured = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def aclose(self):
        """Close the client."""
        pass

    def build_request(self, method, url, headers=None, content=None, timeout=None):
        """Build a request object."""
        return DummyRequest(method=method, url=url, headers=headers, content=content, timeout=timeout)

    async def send(self, request, stream=False):
        """Send a request and return a response."""
        DummyAsyncClient.captured = {
            "method": request.method,
            "url": request.url,
            "headers": request.headers,
            "content": request.content,
            "timeout": request.timeout,
        }
        return DummyResponse()

    async def request(self, method, url, headers=None, content=None, timeout=None):
        DummyAsyncClient.captured = {
            "method": method,
            "url": url,
            "headers": headers,
            "content": content,
            "timeout": timeout,
        }
        return DummyResponse()


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.router_logger = logging.getLogger("devhost.router")
        self.router_logger_level = self.router_logger.level
        self.router_logger.setLevel(logging.ERROR)
        self.httpx_logger = logging.getLogger("httpx")
        self.httpx_logger_level = self.httpx_logger.level
        self.httpx_logger.setLevel(logging.ERROR)
        self.default_config_path = self._write_config({})
        self.config_patch = patch.dict(os.environ, {"DEVHOST_CONFIG": self.default_config_path}, clear=False)
        self.config_patch.start()
        self.env_patch = patch.dict(os.environ, {"DEVHOST_DOMAIN": "localhost"}, clear=False)
        self.env_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.env_patch.stop()
        self.config_patch.stop()
        self.router_logger.setLevel(self.router_logger_level)
        self.httpx_logger.setLevel(self.httpx_logger_level)
        if getattr(self, "default_config_path", None):
            try:
                os.unlink(self.default_config_path)
            except FileNotFoundError:
                pass

    def _write_config(self, data):
        tmp = tempfile.NamedTemporaryFile("w", delete=False)
        json.dump(data, tmp)
        tmp.flush()
        tmp.close()
        return tmp.name

    def test_extract_subdomain(self):
        self.assertEqual(extract_subdomain("hello.localhost"), "hello")
        self.assertEqual(extract_subdomain("api.v1.localhost:1234"), "api.v1")
        self.assertIsNone(extract_subdomain("localhost"))
        self.assertIsNone(extract_subdomain("example.com"))
        self.assertIsNone(extract_subdomain(""))
        self.assertIsNone(extract_subdomain(None))

    def test_extract_subdomain_custom_domain(self):
        with patch.dict(os.environ, {"DEVHOST_DOMAIN": "flask"}, clear=False):
            self.assertEqual(extract_subdomain("hello.flask"), "hello")
            self.assertIsNone(extract_subdomain("hello.localhost"))

    def test_invalid_host_header(self):
        resp = self.client.get("/", headers={"host": "example.com"})
        self.assertEqual(resp.status_code, 400)

    def test_unknown_route(self):
        path = self._write_config({"hello": 3000})
        os.environ["DEVHOST_CONFIG"] = path
        try:
            resp = self.client.get("/", headers={"host": "missing.localhost"})
            self.assertEqual(resp.status_code, 404)
        finally:
            os.unlink(path)
            os.environ["DEVHOST_CONFIG"] = self.default_config_path

    def test_proxy_url_and_headers(self):
        path = self._write_config({"hello": 3000})
        os.environ["DEVHOST_CONFIG"] = path
        captured: dict = {}

        async def fake_request_with_retry(_client, method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = kwargs.get("headers", {})
            captured["content"] = kwargs.get("content")
            return httpx.Response(
                200,
                headers={"content-type": "text/plain", "connection": "keep-alive"},
                content=b"ok",
            )

        try:
            with patch("devhost_cli.router.core.request_with_retry", side_effect=fake_request_with_retry):
                resp = self.client.get("/hello?x=1", headers={"host": "hello.localhost"})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.text, "ok")
            self.assertEqual(captured["url"], "http://127.0.0.1:3000/hello?x=1")
            self.assertNotIn("connection", resp.headers)
        finally:
            os.unlink(path)
            os.environ["DEVHOST_CONFIG"] = self.default_config_path

    def test_forwarded_headers_are_sanitized_and_overwritten(self):
        path = self._write_config({"hello": 3000})
        os.environ["DEVHOST_CONFIG"] = path
        captured: dict = {}

        async def fake_request_with_retry(_client, method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = kwargs.get("headers", {})
            return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"ok")

        try:
            with patch("devhost_cli.router.core.request_with_retry", side_effect=fake_request_with_retry):
                response = self.client.get(
                    "/hello",
                    headers={
                        "host": "hello.localhost",
                        "x-forwarded-for": "8.8.8.8",
                        "x-forwarded-host": "evil.example",
                        "x-forwarded-proto": "https",
                        "x-real-ip": "9.9.9.9",
                    },
                )
            self.assertEqual(response.status_code, 200)
            headers = captured["headers"]
            self.assertEqual(captured["url"], "http://127.0.0.1:3000/hello")
            self.assertEqual(headers.get("X-Forwarded-Host"), "hello.localhost")
            self.assertEqual(headers.get("X-Forwarded-Proto"), "http")
            self.assertNotEqual(headers.get("X-Forwarded-For"), "8.8.8.8")
            self.assertNotEqual(headers.get("X-Real-IP"), "9.9.9.9")
            self.assertEqual(headers.get("X-Forwarded-For"), headers.get("X-Real-IP"))
        finally:
            os.unlink(path)
            os.environ["DEVHOST_CONFIG"] = self.default_config_path


if __name__ == "__main__":
    unittest.main()
