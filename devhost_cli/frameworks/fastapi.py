"""
FastAPI wrapper for Devhost runner.

Provides simplified API for running FastAPI apps with Devhost.
"""

from typing import Any

from ..runner import run as devhost_run


def run_fastapi(
    app: Any,
    name: str | None = None,
    port: int | None = None,
    domain: str = "localhost",
    host: str = "0.0.0.0",
    reload: bool = False,
    log_level: str = "info",
    **kwargs,
):
    """
    Run a FastAPI application with automatic Devhost registration.

    Args:
        app: FastAPI application instance
        name: App name (becomes subdomain). Auto-detected from devhost.yml or directory
        port: Port to run on. Auto-detected if not specified
        domain: Base domain (default: localhost)
        host: Host to bind to (default: 0.0.0.0)
        reload: Enable auto-reload on code changes (default: False)
        log_level: Uvicorn log level (default: info)
        **kwargs: Additional arguments passed to uvicorn.run()

    Example:
        from fastapi import FastAPI
        from devhost_cli.frameworks.fastapi import run_fastapi

        app = FastAPI()

        @app.get('/')
        def index():
            return {"message": "Hello!"}

        if __name__ == '__main__':
            run_fastapi(app)  # Accessible at http://myproject.localhost
    """
    devhost_run(
        app=app,
        name=name,
        port=port,
        domain=domain,
        host=host,
        reload=reload,
        log_level=log_level,
        **kwargs,
    )
