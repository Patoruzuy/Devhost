"""Tests for WSGI middleware."""

import json
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from devhost_cli.middleware.wsgi import DevhostWSGIMiddleware


class TestDevhostWSGIMiddleware(unittest.TestCase):
    """Test cases for DevhostWSGIMiddleware."""

    def setUp(self):
        """Set up test fixtures."""

        # Create a simple WSGI app for testing
        def simple_app(environ, start_response):
            status = "200 OK"
            headers = [("Content-Type", "text/plain")]
            start_response(status, headers)
            return [b"Hello from app"]

        self.simple_app = simple_app
        self.test_routes = {"hello": 3000, "api": "192.168.1.100:8080"}

    def test_initialization(self):
        """Test middleware initialization."""
        middleware = DevhostWSGIMiddleware(self.simple_app)
        self.assertIsNotNone(middleware)
        self.assertEqual(middleware.base_domain, "localhost")
        self.assertEqual(middleware.app, self.simple_app)

    def test_custom_base_domain(self):
        """Test initialization with custom base domain."""
        middleware = DevhostWSGIMiddleware(self.simple_app, base_domain="devhost")
        self.assertEqual(middleware.base_domain, "devhost")

    def test_extract_subdomain_localhost(self):
        """Test subdomain extraction from localhost."""
        middleware = DevhostWSGIMiddleware(self.simple_app)

        # Valid subdomain
        subdomain = middleware._extract_subdomain("hello.localhost")
        self.assertEqual(subdomain, "hello")

        # With port
        subdomain = middleware._extract_subdomain("api.localhost:5000")
        self.assertEqual(subdomain, "api")

        # No subdomain
        subdomain = middleware._extract_subdomain("localhost")
        self.assertIsNone(subdomain)

        # Different domain
        subdomain = middleware._extract_subdomain("example.com")
        self.assertIsNone(subdomain)

    def test_extract_subdomain_custom_domain(self):
        """Test subdomain extraction with custom domain."""
        middleware = DevhostWSGIMiddleware(self.simple_app, base_domain="devhost")

        subdomain = middleware._extract_subdomain("api.devhost")
        self.assertEqual(subdomain, "api")

        subdomain = middleware._extract_subdomain("hello.localhost")
        self.assertIsNone(subdomain)

    def test_parse_target_port(self):
        """Test target parsing with port number."""
        middleware = DevhostWSGIMiddleware(self.simple_app)

        target = middleware._parse_target(3000)
        self.assertEqual(target["scheme"], "http")
        self.assertEqual(target["host"], "127.0.0.1")
        self.assertEqual(target["port"], 3000)

    def test_parse_target_host_port(self):
        """Test target parsing with host:port format."""
        middleware = DevhostWSGIMiddleware(self.simple_app)

        target = middleware._parse_target("192.168.1.100:8080")
        self.assertEqual(target["scheme"], "http")
        self.assertEqual(target["host"], "192.168.1.100")
        self.assertEqual(target["port"], 8080)

    def test_parse_target_url(self):
        """Test target parsing with full URL."""
        middleware = DevhostWSGIMiddleware(self.simple_app)

        target = middleware._parse_target("http://example.com:8000")
        self.assertEqual(target["scheme"], "http")
        self.assertEqual(target["host"], "example.com")
        self.assertEqual(target["port"], 8000)

        target = middleware._parse_target("https://api.example.com")
        self.assertEqual(target["scheme"], "https")
        self.assertEqual(target["host"], "api.example.com")
        self.assertEqual(target["port"], 443)

    def test_parse_target_invalid(self):
        """Test target parsing with invalid input."""
        middleware = DevhostWSGIMiddleware(self.simple_app)

        target = middleware._parse_target("invalid")
        self.assertIsNone(target)

        target = middleware._parse_target("host:invalid")
        self.assertIsNone(target)

    def test_passthrough_no_subdomain(self):
        """Test request passes through when no subdomain."""
        middleware = DevhostWSGIMiddleware(self.simple_app)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/",
            "HTTP_HOST": "localhost:5000",
        }

        start_response = Mock()
        result = middleware(environ, start_response)

        # Should call wrapped app
        self.assertEqual(b"".join(result), b"Hello from app")
        start_response.assert_called_once()

    @patch("devhost_cli.middleware.wsgi.requests.request")
    def test_proxy_request_success(self, mock_request):
        """Test successful proxy request."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.content = b'{"message": "proxied"}'
        mock_request.return_value = mock_response

        middleware = DevhostWSGIMiddleware(self.simple_app)
        middleware._routes = self.test_routes
        # Prevent reloading routes from file
        middleware._load_routes = Mock()

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/api/test",
            "QUERY_STRING": "foo=bar",
            "HTTP_HOST": "hello.localhost:5000",
            "HTTP_USER_AGENT": "TestClient/1.0",
        }

        start_response = Mock()
        result = middleware(environ, start_response)

        # Verify proxy was called
        mock_request.assert_called_once()
        call_args = mock_request.call_args

        # Verify URL
        self.assertEqual(call_args.kwargs["url"], "http://127.0.0.1:3000/api/test?foo=bar")
        self.assertEqual(call_args.kwargs["method"], "GET")

        # Verify response
        self.assertEqual(b"".join(result), b'{"message": "proxied"}')
        start_response.assert_called_once()
        status_arg = start_response.call_args[0][0]
        self.assertEqual(status_arg, "200 OK")

    @patch("devhost_cli.middleware.wsgi.requests.request")
    def test_proxy_request_with_body(self, mock_request):
        """Test proxy request with request body."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.reason = "Created"
        mock_response.headers = {}
        mock_response.content = b""
        mock_request.return_value = mock_response

        middleware = DevhostWSGIMiddleware(self.simple_app)
        middleware._routes = {"api": 8000}
        # Prevent reloading routes from file
        middleware._load_routes = Mock()

        body_data = b'{"name": "test"}'
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/users",
            "HTTP_HOST": "api.localhost",
            "CONTENT_LENGTH": str(len(body_data)),
            "wsgi.input": BytesIO(body_data),
        }

        start_response = Mock()
        middleware(environ, start_response)

        # Verify body was sent
        call_args = mock_request.call_args
        self.assertEqual(call_args.kwargs["data"], body_data)

    @patch("devhost_cli.middleware.wsgi.requests.request")
    def test_proxy_request_error(self, mock_request):
        """Test proxy request with connection error."""
        from requests import RequestException

        mock_request.side_effect = RequestException("Connection refused")

        middleware = DevhostWSGIMiddleware(self.simple_app)
        middleware._routes = {"api": 8000}
        # Prevent reloading routes from file
        middleware._load_routes = Mock()

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/",
            "HTTP_HOST": "api.localhost",
        }

        start_response = Mock()
        result = middleware(environ, start_response)

        # Verify error response
        response_body = b"".join(result)
        response_data = json.loads(response_body)

        self.assertEqual(response_data["error"], "Proxy error")
        self.assertIn("Connection refused", response_data["message"])

        # Verify 502 status
        status_arg = start_response.call_args[0][0]
        self.assertEqual(status_arg, "502 Bad Gateway")

    def test_environ_devhost_info(self):
        """Test that devhost info is added to environ."""
        middleware = DevhostWSGIMiddleware(self.simple_app)
        middleware._routes = self.test_routes
        # Prevent reloading routes from file
        middleware._load_routes = Mock()

        # Use a subdomain that's NOT in routes so it passes through
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/",
            "HTTP_HOST": "notinroutes.localhost",
        }

        start_response = Mock()

        # Patch wrapped app to capture environ
        captured_environ = {}

        def capturing_app(env, start_resp):
            captured_environ.update(env)
            return self.simple_app(env, start_resp)

        middleware.app = capturing_app
        middleware(environ, start_response)

        # Verify devhost info
        self.assertEqual(captured_environ["devhost.subdomain"], "notinroutes")
        self.assertEqual(captured_environ["devhost.routes"], self.test_routes)

    def test_config_loading(self, tmp_path=None):
        """Test config file loading."""
        if tmp_path is None:
            import tempfile

            tmp_path = Path(tempfile.mkdtemp())

        config_file = tmp_path / "devhost.json"
        config_file.write_text(json.dumps({"test": 1234, "api": 5000}))

        middleware = DevhostWSGIMiddleware(self.simple_app, config_path=str(config_file))
        middleware._load_routes()

        self.assertEqual(middleware._routes, {"test": 1234, "api": 5000})


if __name__ == "__main__":
    unittest.main()
