"""
Django integration example with Devhost.

This demonstrates using Devhost WSGI middleware with Django applications
to enable subdomain routing.

Usage:
    # Install devhost and Django
    pip install devhost django

    # Run the example
    python examples/example_django.py

    # Configure routes
    devhost add blog 8000
    devhost add api 8080

    # Access:
    # http://blog.localhost:8000 - proxies to localhost:8000
    # http://api.localhost:8000 - proxies to localhost:8080
    # http://localhost:8000 - regular Django app (no proxy)

Note: This is a minimal Django app for demonstration.
For production, use proper Django project structure.
"""

import sys

import django
from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler
from django.http import JsonResponse
from django.urls import path

from devhost_cli.middleware.wsgi import DevhostWSGIMiddleware

# Configure Django settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="dev-secret-key-not-for-production",
        ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=["*"],
        MIDDLEWARE=[],
    )
    django.setup()


# Views
def index(request):
    """Root endpoint with subdomain info."""
    subdomain = request.environ.get("devhost.subdomain")
    target = request.environ.get("devhost.target")
    routes = request.environ.get("devhost.routes", {})

    return JsonResponse(
        {
            "app": "Django with Devhost",
            "subdomain": subdomain,
            "target": target,
            "configured_routes": list(routes.keys()),
            "message": "Subdomain routing enabled!" if subdomain else "No subdomain - regular Django app",
        }
    )


def users(request):
    """Example API endpoint."""
    return JsonResponse({"users": ["alice", "bob", "charlie"]})


def status(request):
    """Status endpoint."""
    return JsonResponse(
        {
            "status": "ok",
            "framework": "Django",
            "devhost": "enabled",
        }
    )


def health(request):
    """Health check endpoint."""
    return JsonResponse({"status": "healthy"})


# URL patterns
urlpatterns = [
    path("", index),
    path("api/users/", users),
    path("api/status/", status),
    path("health/", health),
]


# Create WSGI application with Devhost middleware
application = WSGIHandler()
application = DevhostWSGIMiddleware(application)


if __name__ == "__main__":
    print("=" * 60)
    print("Django + Devhost Example")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET / - Root with subdomain info")
    print("  GET /api/users/ - Example users API")
    print("  GET /api/status/ - Application status")
    print("  GET /health/ - Health check")
    print("\nProxy Setup:")
    print("  1. devhost add blog 8000")
    print("  2. devhost add api 8080")
    print("  3. Visit http://blog.localhost:8000")
    print("\nDirect Access:")
    print("  Visit http://localhost:8000 (no proxy)")
    print("\nRunning server...")
    print("=" * 60)

    # Run with Django development server
    from django.core.management import execute_from_command_line

    execute_from_command_line([sys.argv[0], "runserver", "127.0.0.1:8000"])
