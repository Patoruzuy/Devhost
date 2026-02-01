"""
Flask integration example with Devhost.

This demonstrates using Devhost WSGI middleware with Flask applications
to enable subdomain routing.

Usage:
    # Install devhost and Flask
    pip install devhost flask

    # Run the example
    python examples/example_flask.py

    # Configure routes
    devhost add myapp 3000

    # Access:
    # http://myapp.localhost:5000 - proxies to localhost:3000
    # http://localhost:5000 - regular Flask app (no proxy)
"""

from flask import Flask, jsonify, request

from devhost_cli.middleware.wsgi import DevhostWSGIMiddleware

# Create Flask app
app = Flask(__name__)


# Add Devhost WSGI middleware
app.wsgi_app = DevhostWSGIMiddleware(app.wsgi_app)


@app.route("/")
def index():
    """Root endpoint with subdomain info."""
    # Access Devhost info from environ
    subdomain = request.environ.get("devhost.subdomain")
    target = request.environ.get("devhost.target")
    routes = request.environ.get("devhost.routes", {})

    return jsonify(
        {
            "app": "Flask with Devhost",
            "subdomain": subdomain,
            "target": target,
            "configured_routes": list(routes.keys()),
            "message": "Subdomain routing enabled!" if subdomain else "No subdomain - regular Flask app",
        }
    )


@app.route("/api/users")
def users():
    """Example API endpoint."""
    return jsonify({"users": ["alice", "bob", "charlie"]})


@app.route("/api/status")
def status():
    """Status endpoint."""
    return jsonify(
        {
            "status": "ok",
            "framework": "Flask",
            "devhost": "enabled",
        }
    )


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    print("=" * 60)
    print("Flask + Devhost Example")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET / - Root with subdomain info")
    print("  GET /api/users - Example users API")
    print("  GET /api/status - Application status")
    print("  GET /health - Health check")
    print("\nProxy Setup:")
    print("  1. devhost add myapp 3000")
    print("  2. devhost add api 8000")
    print("  3. Visit http://myapp.localhost:5000")
    print("\nDirect Access:")
    print("  Visit http://localhost:5000 (no proxy)")
    print("=" * 60)

    app.run(host="127.0.0.1", port=5000, debug=True)
