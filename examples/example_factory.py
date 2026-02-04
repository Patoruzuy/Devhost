"""
Factory function example with Devhost.

This demonstrates using the create_devhost_app() factory to get a
complete FastAPI application with subdomain routing and proxy endpoints.

Usage:
    pip install devhost
    python examples/example_factory.py

    # Then configure routes
    devhost add hello 3000
    devhost add api 8000

    # Access via:
    # http://hello.localhost (proxies to localhost:3000)
    # http://api.localhost (proxies to localhost:8000)
"""

import uvicorn

from devhost_cli.factory import create_devhost_app

# Create a complete Devhost-enabled FastAPI app
# Includes subdomain routing, proxy endpoints, and health checks
app = create_devhost_app()


# Optionally add custom routes
@app.get("/custom")
async def custom_endpoint():
    """Custom endpoint alongside Devhost functionality"""
    return {"message": "This is a custom endpoint", "devhost": "enabled"}


if __name__ == "__main__":
    print("Starting Devhost factory example...")
    print("Endpoints:")
    print("  GET /health - Health check")
    print("  GET /routes - List configured routes")
    print("  GET /mappings - Routes with health status")
    print("  GET /custom - Custom endpoint")
    print("\nConfigure routes with: devhost add <name> <port>")

    uvicorn.run(app, host="127.0.0.1", port=7777)
