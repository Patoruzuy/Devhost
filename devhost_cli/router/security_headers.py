"""Security headers middleware for Devhost router

Optional security headers that can be enabled via DEVHOST_SECURITY_HEADERS=1
"""

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses

    Enabled via DEVHOST_SECURITY_HEADERS=1 environment variable.
    Default: Disabled (opt-in to avoid breaking existing deployments)

    Headers added when enabled:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: SAMEORIGIN
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Content-Security-Policy: default-src 'self' (optional, configurable)
    """

    def __init__(self, app, enabled: bool = None):
        super().__init__(app)
        if enabled is None:
            enabled = os.getenv("DEVHOST_SECURITY_HEADERS", "0").lower() in ("1", "true", "yes", "on")
        self.enabled = enabled

        # Allow customization via environment variables
        self.headers = {
            "X-Content-Type-Options": os.getenv("DEVHOST_HEADER_CONTENT_TYPE_OPTIONS", "nosniff"),
            "X-Frame-Options": os.getenv("DEVHOST_HEADER_FRAME_OPTIONS", "SAMEORIGIN"),
            "X-XSS-Protection": os.getenv("DEVHOST_HEADER_XSS_PROTECTION", "1; mode=block"),
            "Referrer-Policy": os.getenv("DEVHOST_HEADER_REFERRER_POLICY", "strict-origin-when-cross-origin"),
        }

        # Optional CSP header (disabled by default - can break apps)
        csp = os.getenv("DEVHOST_HEADER_CSP")
        if csp:
            self.headers["Content-Security-Policy"] = csp

    async def dispatch(self, request, call_next):
        """Add security headers to response"""
        response: Response = await call_next(request)

        if self.enabled:
            for header, value in self.headers.items():
                response.headers[header] = value

        return response


def is_security_headers_enabled() -> bool:
    """Check if security headers are enabled

    Returns:
        True if DEVHOST_SECURITY_HEADERS=1, False otherwise
    """
    return os.getenv("DEVHOST_SECURITY_HEADERS", "0").lower() in ("1", "true", "yes", "on")
