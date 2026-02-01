import json
import logging
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from router.app import app, extract_subdomain


class DummyResponse:
    def __init__(self):
        self.content = b"ok"
        self.status_code = 200
        self.headers = {"content-type": "text/plain", "connection": "keep-alive"}


class DummyAsyncClient:
    captured = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

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
        DummyAsyncClient.captured = None
        try:
            with patch("router.app.httpx.AsyncClient", DummyAsyncClient):
                resp = self.client.get("/hello?x=1", headers={"host": "hello.localhost"})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.text, "ok")
            self.assertIsNotNone(DummyAsyncClient.captured)
            self.assertEqual(DummyAsyncClient.captured["url"], "http://127.0.0.1:3000/hello?x=1")
            self.assertNotIn("connection", resp.headers)
        finally:
            os.unlink(path)
            os.environ["DEVHOST_CONFIG"] = self.default_config_path


if __name__ == "__main__":
    unittest.main()
