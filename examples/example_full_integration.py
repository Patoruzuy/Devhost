"""
Full-featured example combining factory functions with custom routes.

This demonstrates using Devhost factory functions to enable subdomain routing,
then adding your own custom application logic on top.

Usage:
    pip install devhost
    python examples/example_full_integration.py

    # Configure routes
    devhost add frontend 3000
    devhost add backend 8000

    # Access:
    # http://frontend.localhost - proxies to localhost:3000
    # http://backend.localhost - proxies to localhost:8000
    # http://localhost:7777/api/status - custom endpoint (no proxy)
"""

import uvicorn
from fastapi import APIRouter, FastAPI

from devhost_cli.factory import create_proxy_router, enable_subdomain_routing

# Option 1: Start with your own FastAPI app and add Devhost routing
app = FastAPI(title="My Application", description="Custom app with Devhost subdomain routing", version="1.0.0")

# Enable subdomain routing for your app
enable_subdomain_routing(app)

# Add Devhost proxy endpoints
proxy_router = create_proxy_router()
app.include_router(proxy_router)


# Add your custom application routes
@app.get("/")
async def root():
    """Your custom root endpoint"""
    return {
        "app": "My Custom Application",
        "devhost": "enabled",
        "message": "Use subdomains to access proxied services",
    }


@app.get("/api/status")
async def status():
    """Custom status endpoint"""
    return {"status": "running", "features": ["subdomain routing", "proxy support", "custom APIs"]}


@app.get("/api/config")
async def config():
    """Example config endpoint"""
    return {"environment": "development", "routing": "subdomain-based", "proxy": "enabled"}


# Custom API router example
api_router = APIRouter(prefix="/api/v1", tags=["api"])


@api_router.get("/items")
async def get_items():
    """Example items endpoint"""
    return {"items": ["item1", "item2", "item3"]}


@api_router.get("/users")
async def get_users():
    """Example users endpoint"""
    return {"users": ["alice", "bob", "charlie"]}


app.include_router(api_router)


if __name__ == "__main__":
    print("=" * 60)
    print("Full-featured Devhost Integration Example")
    print("=" * 60)
    print("\nCustom Endpoints (direct access):")
    print("  GET / - Custom root")
    print("  GET /api/status - Application status")
    print("  GET /api/config - Configuration")
    print("  GET /api/v1/items - Items API")
    print("  GET /api/v1/users - Users API")
    print("\nDevhost Endpoints (for management):")
    print("  GET /health - Health check with route count")
    print("  GET /routes - List all configured routes")
    print("  GET /mappings - Routes with TCP health checks")
    print("\nProxy Behavior:")
    print("  Any request with subdomain routes to configured target")
    print("  Example: http://frontend.localhost → localhost:3000")
    print("\nQuick Start:")
    print("  1. devhost add frontend 3000")
    print("  2. devhost add backend 8000")
    print("  3. Visit http://frontend.localhost")
    print("=" * 60)

    uvicorn.run(app, host="127.0.0.1", port=7777)
