"""
WSGI middleware for Devhost subdomain routing.

This middleware adds subdomain routing capability to WSGI applications
like Flask and Django. It wraps the WSGI application and provides
subdomain-aware request handling.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests


class DevhostWSGIMiddleware:
    """
    WSGI middleware for subdomain routing with Devhost.

    This middleware intercepts requests and routes them based on subdomain
    configuration, similar to the ASGI middleware but for synchronous
    WSGI applications.

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
    ):
        """
        Initialize WSGI middleware.

        Args:
            app: The WSGI application to wrap
            config_path: Optional path to devhost.json config file
            base_domain: Optional base domain (default: localhost)
        """
        self.app = app
        self.config_path = config_path or self._find_config()
        self.base_domain = base_domain or "localhost"
        self._routes: dict[str, Any] = {}
        self._load_routes()

    def _find_config(self) -> str:
        """Find devhost.json config file."""
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

        # Default path
        return "devhost.json"

    def _load_routes(self) -> None:
        """Load routes from devhost.json config file."""
        try:
            config_path = Path(self.config_path)
            if config_path.exists():
                with open(config_path) as f:
                    self._routes = json.load(f)
        except (OSError, json.JSONDecodeError):
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

    def __call__(self, environ: dict[str, Any], start_response: Callable) -> Any:
        """
        WSGI application callable.

        Args:
            environ: WSGI environment dict
            start_response: WSGI start_response callable

        Returns:
            Response iterable
        """
        # Reload routes on each request (for hot reload)
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
                environ["devhost.target"] = target
                return self._proxy_request(environ, start_response, target)

        # No subdomain routing, pass through to wrapped app
        return self.app(environ, start_response)

    def _proxy_request(self, environ: dict[str, Any], start_response: Callable, target: dict[str, Any]) -> Any:
        """
        Proxy request to target service.

        Args:
            environ: WSGI environment dict
            start_response: WSGI start_response callable
            target: Target service info (scheme, host, port)

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

        # Prepare headers
        headers = {}
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                header_name = key[5:].replace("_", "-").title()
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

        # Make proxy request
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                data=body,
                allow_redirects=False,
                timeout=30,
            )

            # Prepare response headers
            response_headers = [(name, value) for name, value in response.headers.items()]

            # Start response
            status = f"{response.status_code} {response.reason}"
            start_response(status, response_headers)

            # Return response body
            return [response.content]

        except requests.RequestException as e:
            # Error response
            status = "502 Bad Gateway"
            response_headers = [("Content-Type", "application/json")]
            start_response(status, response_headers)

            error_body = json.dumps({"error": "Proxy error", "message": str(e)}).encode()
            return [error_body]
