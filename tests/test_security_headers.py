"""Tests for security headers middleware (L-09)

Tests that security headers are:
- Disabled by default (opt-in)
- Can be enabled via environment variable
- Include all expected headers
- Are customizable via environment variables
"""

import os
import unittest
from unittest.mock import MagicMock

from starlette.responses import Response

from devhost_cli.router.security_headers import SecurityHeadersMiddleware, is_security_headers_enabled


class TestSecurityHeadersMiddleware(unittest.IsolatedAsyncioTestCase):
    """Test security headers middleware"""

    def tearDown(self):
        """Clean up environment variables"""
        os.environ.pop("DEVHOST_SECURITY_HEADERS", None)
        os.environ.pop("DEVHOST_HEADER_CONTENT_TYPE_OPTIONS", None)
        os.environ.pop("DEVHOST_HEADER_FRAME_OPTIONS", None)
        os.environ.pop("DEVHOST_HEADER_XSS_PROTECTION", None)
        os.environ.pop("DEVHOST_HEADER_REFERRER_POLICY", None)
        os.environ.pop("DEVHOST_HEADER_CSP", None)

    async def test_headers_disabled_by_default(self):
        """Security headers should be disabled by default (opt-in)"""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        # Create mock request and response
        request = MagicMock()
        response = Response(content="test", status_code=200)

        async def call_next(req):
            return response

        # Dispatch request
        result = await middleware.dispatch(request, call_next)

        # Headers should NOT be added when disabled
        self.assertNotIn("X-Content-Type-Options", result.headers)
        self.assertNotIn("X-Frame-Options", result.headers)
        self.assertNotIn("X-XSS-Protection", result.headers)
        self.assertNotIn("Referrer-Policy", result.headers)

    async def test_headers_enabled_via_env_var(self):
        """Security headers can be enabled via DEVHOST_SECURITY_HEADERS=1"""
        os.environ["DEVHOST_SECURITY_HEADERS"] = "1"

        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        # Create mock request and response
        request = MagicMock()
        response = Response(content="test", status_code=200)

        async def call_next(req):
            return response

        # Dispatch request
        result = await middleware.dispatch(request, call_next)

        # All headers should be present
        self.assertEqual(result.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(result.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(result.headers["X-XSS-Protection"], "1; mode=block")
        self.assertEqual(result.headers["Referrer-Policy"], "strict-origin-when-cross-origin")

    async def test_custom_header_values(self):
        """Custom header values via environment variables"""
        os.environ["DEVHOST_SECURITY_HEADERS"] = "1"
        os.environ["DEVHOST_HEADER_FRAME_OPTIONS"] = "DENY"
        os.environ["DEVHOST_HEADER_REFERRER_POLICY"] = "no-referrer"

        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        # Create mock request and response
        request = MagicMock()
        response = Response(content="test", status_code=200)

        async def call_next(req):
            return response

        # Dispatch request
        result = await middleware.dispatch(request, call_next)

        # Check custom values
        self.assertEqual(result.headers["X-Frame-Options"], "DENY")
        self.assertEqual(result.headers["Referrer-Policy"], "no-referrer")

    async def test_optional_csp_header(self):
        """CSP header is optional and only added when configured"""
        os.environ["DEVHOST_SECURITY_HEADERS"] = "1"
        os.environ["DEVHOST_HEADER_CSP"] = "default-src 'self'"

        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        # Create mock request and response
        request = MagicMock()
        response = Response(content="test", status_code=200)

        async def call_next(req):
            return response

        # Dispatch request
        result = await middleware.dispatch(request, call_next)

        # CSP should be present
        self.assertEqual(result.headers["Content-Security-Policy"], "default-src 'self'")

    async def test_explicit_enable_in_constructor(self):
        """Middleware can be explicitly enabled in constructor"""
        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app, enabled=True)

        # Create mock request and response
        request = MagicMock()
        response = Response(content="test", status_code=200)

        async def call_next(req):
            return response

        # Dispatch request
        result = await middleware.dispatch(request, call_next)

        # Headers should be present
        self.assertIn("X-Content-Type-Options", result.headers)
        self.assertIn("X-Frame-Options", result.headers)


class TestSecurityHeadersConfig(unittest.TestCase):
    """Test security headers configuration"""

    def tearDown(self):
        """Clean up environment variables"""
        os.environ.pop("DEVHOST_SECURITY_HEADERS", None)

    def test_security_headers_disabled_by_default(self):
        """is_security_headers_enabled() returns False by default"""
        os.environ.pop("DEVHOST_SECURITY_HEADERS", None)

        result = is_security_headers_enabled()

        self.assertFalse(result)

    def test_security_headers_enabled_with_1(self):
        """is_security_headers_enabled() returns True when set to '1'"""
        os.environ["DEVHOST_SECURITY_HEADERS"] = "1"

        result = is_security_headers_enabled()

        self.assertTrue(result)

    def test_security_headers_various_true_values(self):
        """Accept various true values"""
        for value in ["1", "true", "True", "TRUE", "yes", "Yes", "on", "On"]:
            os.environ["DEVHOST_SECURITY_HEADERS"] = value

            result = is_security_headers_enabled()

            self.assertTrue(result, f"Failed for value: {value}")


if __name__ == "__main__":
    unittest.main()
