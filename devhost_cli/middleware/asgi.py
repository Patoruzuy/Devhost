"""
ASGI middleware for subdomain-based routing in FastAPI, Starlette, etc.
"""

from collections.abc import Callable

from devhost_cli.router.cache import RouteCache
from devhost_cli.router.utils import extract_subdomain, load_domain, parse_target


class DevhostMiddleware:
    """
    ASGI middleware for subdomain-based request routing.

    Automatically routes requests based on subdomain to local development services.
    Integrates with FastAPI, Starlette, and other ASGI frameworks.

    Example:
        from fastapi import FastAPI
        from devhost import DevhostMiddleware

        app = FastAPI()
        app.add_middleware(DevhostMiddleware)
    """

    def __init__(self, app: Callable):
        """
        Initialize the middleware.

        Args:
            app: ASGI application callable
        """
        self.app = app
        self.route_cache = RouteCache()

    async def __call__(self, scope: dict, receive: Callable, send: Callable):
        """
        ASGI middleware callable.

        Intercepts requests and adds devhost routing information to scope.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract subdomain from Host header
        headers = dict(scope.get("headers", []))
        host_header = headers.get(b"host", b"").decode("utf-8", errors="ignore")

        base_domain = load_domain()
        subdomain = extract_subdomain(host_header, base_domain)

        # Add devhost info to scope
        scope["devhost"] = {
            "subdomain": subdomain,
            "domain": base_domain,
            "target": None,
        }

        if subdomain:
            routes = await self.route_cache.get_routes()
            target_value = routes.get(subdomain)
            target = parse_target(target_value)
            if target:
                scheme, host, port = target
                scope["devhost"]["target"] = {
                    "scheme": scheme,
                    "host": host,
                    "port": port,
                    "url": f"{scheme}://{host}:{port}",
                    "raw": target_value,
                }

        await self.app(scope, receive, send)
