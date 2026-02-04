"""
Django wrapper for Devhost runner.

Provides simplified API for running Django apps with Devhost.
"""

from typing import Any

from ..runner import run as devhost_run


def run_django(
    application: Any | None = None,
    name: str | None = None,
    port: int | None = None,
    domain: str = "localhost",
    host: str = "127.0.0.1",
    **kwargs,
):
    """
    Run a Django application with automatic Devhost registration.

    If no application is provided, it will attempt to get the WSGI application
    from Django's default WSGI handler.

    Args:
        application: Django WSGI application (optional)
        name: App name (becomes subdomain). Auto-detected from devhost.yml or directory
        port: Port to run on. Auto-detected if not specified
        domain: Base domain (default: localhost)
        host: Host to bind to (default: 127.0.0.1 for security)
        **kwargs: Additional arguments

    Example:
        # In wsgi.py or manage.py
        from devhost_cli.frameworks.django import run_django

        if __name__ == '__main__':
            run_django()  # Accessible at http://myproject.localhost

    Or with explicit application:
        from django.core.wsgi import get_wsgi_application
        from devhost_cli.frameworks.django import run_django

        application = get_wsgi_application()

        if __name__ == '__main__':
            run_django(application)
    """
    if application is None:
        try:
            from django.core.wsgi import get_wsgi_application

            application = get_wsgi_application()
        except ImportError:
            from ..utils import msg_error

            msg_error("Django not installed or DJANGO_SETTINGS_MODULE not set")
            raise

    devhost_run(
        app=application,
        name=name,
        port=port,
        domain=domain,
        host=host,
        **kwargs,
    )
