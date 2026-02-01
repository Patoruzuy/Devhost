"""
Factory functions for easy Devhost integration.
"""

from collections.abc import Callable

from fastapi import FastAPI

from devhost_cli.middleware import DevhostMiddleware
from devhost_cli.router import create_app


def create_devhost_app(config_path: str | None = None) -> FastAPI:
    """
    Create a standalone Devhost router application.

    This creates a complete FastAPI application that acts as a reverse proxy,
    routing requests based on subdomain to configured local services.

    Args:
        config_path: Optional path to devhost.json config file

    Returns:
        Configured FastAPI application

    Example:
        from devhost import create_devhost_app
        import uvicorn

        app = create_devhost_app()
        uvicorn.run(app, host="127.0.0.1", port=5555)
    """
    return create_app()


def enable_subdomain_routing(app: FastAPI | Callable, config_path: str | None = None) -> FastAPI | Callable:
    """
    Enable subdomain routing for an existing ASGI application.

    Adds Devhost middleware to your application, making subdomain information
    available in request.scope["devhost"].

    Args:
        app: ASGI application (FastAPI, Starlette, etc.)
        config_path: Optional path to devhost.json config file

    Returns:
        The same application with middleware added

    Example:
        from fastapi import FastAPI, Request
        from devhost import enable_subdomain_routing

        app = FastAPI()
        enable_subdomain_routing(app)

        @app.get("/")
        def read_root(request: Request):
            subdomain = request.scope.get("devhost", {}).get("subdomain")
            return {"subdomain": subdomain}
    """
    if hasattr(app, "add_middleware"):
        # FastAPI/Starlette
        app.add_middleware(DevhostMiddleware, config_path=config_path)
    else:
        # Generic ASGI app - wrap it
        return DevhostMiddleware(app, config_path=config_path)
    return app


def create_proxy_router(config_path: str | None = None) -> FastAPI:
    """
    Create a proxy router application (alias for create_devhost_app).

    Args:
        config_path: Optional path to devhost.json config file

    Returns:
        Configured FastAPI proxy application
    """
    return create_devhost_app(config_path)
