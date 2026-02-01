"""Tests for factory functions"""

import unittest

from fastapi import FastAPI

from devhost_cli import create_devhost_app, create_proxy_router, enable_subdomain_routing
from devhost_cli.middleware import DevhostMiddleware


class FactoryTests(unittest.TestCase):
    def test_create_devhost_app(self):
        """Test creating a standalone Devhost app"""
        app = create_devhost_app()
        self.assertIsInstance(app, FastAPI)

    def test_create_proxy_router(self):
        """Test creating a proxy router (alias)"""
        app = create_proxy_router()
        self.assertIsInstance(app, FastAPI)

    def test_enable_subdomain_routing_fastapi(self):
        """Test enabling subdomain routing on FastAPI app"""
        app = FastAPI()
        result = enable_subdomain_routing(app)
        self.assertIs(result, app)
        # Verify middleware was added by checking user_middleware
        middleware_classes = [m.cls for m in app.user_middleware]
        self.assertIn(DevhostMiddleware, middleware_classes)

    def test_enable_subdomain_routing_generic_asgi(self):
        """Test enabling subdomain routing on generic ASGI app"""

        async def simple_asgi_app(scope, receive, send):
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [[b"content-type", b"text/plain"]],
                }
            )
            await send({"type": "http.response.body", "body": b"Hello"})

        wrapped = enable_subdomain_routing(simple_asgi_app)
        self.assertIsInstance(wrapped, DevhostMiddleware)


if __name__ == "__main__":
    unittest.main()
