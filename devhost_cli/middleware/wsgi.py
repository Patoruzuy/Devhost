"""
WSGI middleware for Devhost subdomain routing.

This middleware adds subdomain routing capability to WSGI applications
like Flask and Django. It wraps the WSGI application and provides
subdomain-aware request handling with connection pooling, SSRF protection,
retry logic, and metrics tracking.
"""

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class DevhostWSGIMiddleware:
    """
    WSGI middleware for subdomain routing with Devhost.

    This middleware intercepts requests and routes them based on subdomain
    configuration, similar to the ASGI middleware but for synchronous
    WSGI applications.

    Features:
    - Connection pooling with httpx for better performance
    - SSRF protection to block malicious targets
    - Retry logic with exponential backoff for transient failures
    - Metrics tracking for monitoring
    - Rate-limited config reloading

    Usage:
        from flask import Flask
        from devhost_cli.middleware.wsgi import DevhostWSGIMiddleware

        app = Flask(__name__)
        app.wsgi_app = DevhostWSGIMiddleware(app.wsgi_app)
    """

    def __init__(
        self,
        app: Callable,
        config_path: str | None = None,
        base_domain: str | None = None,
        max_retries: int = 3,
        timeout: float = 30.0,
    ):
        """
        Initialize WSGI middleware.

        Args:
            app: The WSGI application to wrap
            config_path: Optional path to devhost.json config file
            base_domain: Optional base domain (default: localhost)
            max_retries: Maximum number of retry attempts for transient failures
            timeout: Request timeout in seconds
        """
        self.app = app
        self.config_path = config_path or self._find_config()
        self.base_domain = base_domain or "localhost"
        self.max_retries = max_retries
        self.timeout = timeout
        self._routes: dict[str, Any] = {}
        self._last_reload = 0.0
        self._reload_interval = 2.0  # Reload config at most every 2 seconds

        # Initialize httpx client with connection pooling
        self._client = httpx.Client(
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0,
            ),
            timeout=timeout,
            follow_redirects=False,
        )

        # Initialize metrics
        self._metrics = {
            "requests_total": 0,
            "requests_proxied": 0,
            "requests_failed": 0,
            "ssrf_blocks": 0,
        }

        self._load_routes()

    def __del__(self):
        """Clean up resources."""
        try:
            self._client.close()
        except Exception:
            pass

    def _find_config(self) -> str:
        """Find devhost.json config file."""
        # Check ~/.devhost/devhost.json first (correct priority)
        home_config = Path.home() / ".devhost" / "devhost.json"
        if home_config.exists():
            return str(home_config)

        # Check current directory
        config_file = Path("devhost.json")
        if config_file.exists():
            return str(config_file)

        # Check parent directories
        current = Path.cwd()
        for parent in current.parents:
            config_file = parent / "devhost.json"
            if config_file.exists():
                return str(config_file)

        # Default to home config path
        return str(home_config)

    def _load_routes(self) -> None:
        """Load routes from devhost.json config file with rate limiting."""
        current_time = time.time()
        if current_time - self._last_reload < self._reload_interval:
            return

        self._last_reload = current_time

        try:
            config_path = Path(self.config_path)
            if config_path.exists():
                with open(config_path) as f:
                    self._routes = json.load(f)
                logger.debug(f"Loaded {len(self._routes)} routes from {config_path}")
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load routes: {e}")
            self._routes = {}

    def _extract_subdomain(self, host: str) -> str | None:
        """
        Extract subdomain from Host header.

        Args:
            host: Host header value (e.g., "api.localhost:5000")

        Returns:
            Subdomain name or None if no subdomain
        """
        if not host:
            return None

        # Remove port if present
        host_without_port = host.split(":")[0]

        # Check if it matches base domain pattern
        if not host_without_port.endswith(f".{self.base_domain}"):
            return None

        # Extract subdomain
        subdomain = host_without_port[: -(len(self.base_domain) + 1)]
        return subdomain if subdomain else None

    def _parse_target(self, target: Any) -> dict[str, Any] | None:
        """
        Parse target configuration.

        Args:
            target: Port number, host:port string, or URL

        Returns:
            Dict with scheme, host, port or None
        """
        if isinstance(target, int):
            return {"scheme": "http", "host": "127.0.0.1", "port": target}

        if isinstance(target, str):
            if target.startswith("http://") or target.startswith("https://"):
                # Full URL
                from urllib.parse import urlparse

                parsed = urlparse(target)
                return {
                    "scheme": parsed.scheme,
                    "host": parsed.hostname or "127.0.0.1",
                    "port": parsed.port or (443 if parsed.scheme == "https" else 80),
                }
            elif ":" in target:
                # host:port format
                host, port_str = target.split(":", 1)
                try:
                    return {"scheme": "http", "host": host, "port": int(port_str)}
                except ValueError:
                    return None

        return None

    def _validate_upstream_target(self, target: dict[str, Any]) -> bool:
        """
        Validate upstream target for SSRF protection.

        Args:
            target: Target service info (scheme, host, port)

        Returns:
            True if target is safe, False otherwise
        """
        try:
            from devhost_cli.router.security import validate_upstream_target

            host = target["host"]
            port = target["port"]
            valid, error_msg = validate_upstream_target(host, port)
            if not valid:
                logger.warning(f"SSRF validation failed for {target}: {error_msg}")
                self._metrics["ssrf_blocks"] += 1
            return valid
        except Exception as e:
            logger.warning(f"SSRF validation failed for {target}: {e}")
            self._metrics["ssrf_blocks"] += 1
            return False

    def __call__(self, environ: dict[str, Any], start_response: Callable) -> Any:
        """
        WSGI application callable.

        Args:
            environ: WSGI environment dict
            start_response: WSGI start_response callable

        Returns:
            Response iterable
        """
        self._metrics["requests_total"] += 1

        # Reload routes with rate limiting
        self._load_routes()

        # Extract subdomain from Host header
        host = environ.get("HTTP_HOST", "")
        subdomain = self._extract_subdomain(host)

        # Add devhost info to environ
        environ["devhost.subdomain"] = subdomain
        environ["devhost.routes"] = self._routes

        # If subdomain matches a route, proxy the request
        if subdomain and subdomain in self._routes:
            target = self._parse_target(self._routes[subdomain])
            if target:
                # SSRF protection check
                if not self._validate_upstream_target(target):
                    status = "403 Forbidden"
                    response_headers = [("Content-Type", "application/json")]
                    start_response(status, response_headers)
                    error_body = json.dumps(
                        {
                            "error": "Forbidden",
                            "message": f"Target {target['host']}:{target['port']} is not allowed (SSRF protection)",
                        }
                    ).encode()
                    return [error_body]

                environ["devhost.target"] = target
                return self._proxy_request(environ, start_response, target, subdomain)

        # No subdomain routing, pass through to wrapped app
        return self.app(environ, start_response)

    def _proxy_request(
        self,
        environ: dict[str, Any],
        start_response: Callable,
        target: dict[str, Any],
        subdomain: str,
    ) -> Any:
        """
        Proxy request to target service with retry logic.

        Args:
            environ: WSGI environment dict
            start_response: WSGI start_response callable
            target: Target service info (scheme, host, port)
            subdomain: Subdomain name for logging

        Returns:
            Response iterable
        """
        # Build target URL
        scheme = target["scheme"]
        host = target["host"]
        port = target["port"]
        path = environ.get("PATH_INFO", "/")
        query = environ.get("QUERY_STRING", "")

        url = f"{scheme}://{host}:{port}{path}"
        if query:
            url += f"?{query}"

        # Prepare headers (filter hop-by-hop headers)
        headers = {}
        hop_by_hop = {
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
        }
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                header_name = key[5:].replace("_", "-").lower()
                if header_name not in hop_by_hop:
                    headers[header_name] = value

        # Get request method and body
        method = environ.get("REQUEST_METHOD", "GET")
        content_length = environ.get("CONTENT_LENGTH")
        body = None
        if content_length:
            try:
                body = environ["wsgi.input"].read(int(content_length))
            except (ValueError, KeyError):
                pass

        # Retry loop for transient failures
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Proxying {method} {url} (attempt {attempt + 1}/{self.max_retries})")

                response = self._client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body,
                )

                # Success - prepare response
                self._metrics["requests_proxied"] += 1

                # Filter hop-by-hop headers from response
                response_headers = [
                    (name, value) for name, value in response.headers.items() if name.lower() not in hop_by_hop
                ]

                # Start response
                status = f"{response.status_code} {response.reason_phrase}"
                start_response(status, response_headers)

                # Return response body
                return [response.content]

            except httpx.ConnectError as e:
                # Transient connection error - retry with exponential backoff
                last_error = e
                if attempt < self.max_retries - 1:
                    backoff = 0.1 * (2**attempt)  # 100ms, 200ms, 400ms
                    logger.debug(f"Connection error, retrying in {backoff}s: {e}")
                    time.sleep(backoff)
                    continue

            except Exception as e:
                # Non-retryable error
                last_error = e
                break

        # All retries exhausted or non-retryable error
        self._metrics["requests_failed"] += 1
        logger.warning(f"Proxy request failed after {self.max_retries} attempts: {last_error}")

        status = "502 Bad Gateway"
        response_headers = [("Content-Type", "application/json")]
        start_response(status, response_headers)

        error_body = json.dumps(
            {
                "error": "Proxy error",
                "message": str(last_error),
                "subdomain": subdomain,
                "target": f"{host}:{port}",
            }
        ).encode()
        return [error_body]

    def get_metrics(self) -> dict[str, int]:
        """Get current metrics."""
        return self._metrics.copy()
