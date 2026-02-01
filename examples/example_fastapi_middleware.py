"""
FastAPI middleware integration example with Devhost.

This demonstrates adding Devhost middleware to an existing FastAPI application.
The middleware adds subdomain routing capability to your app.

Usage:
    pip install devhost
    python examples/example_fastapi_middleware.py

    # Configure routes
    devhost add myapp 3000

    # Access your app at: http://myapp.localhost
"""

import uvicorn
from fastapi import FastAPI, Request
from devhost_cli.middleware.asgi import DevhostMiddleware

# Create your FastAPI app as usual
app = FastAPI(title="My App with Devhost")

# Add Devhost middleware for subdomain routing
app.add_middleware(DevhostMiddleware)


@app.get("/")
async def root(request: Request):
    """Root endpoint with subdomain information"""
    # Access Devhost info from request scope
    devhost_info = request.scope.get("devhost", {})
    
    return {
        "message": "Hello from FastAPI with Devhost!",
        "subdomain": devhost_info.get("subdomain"),
        "target": devhost_info.get("target"),
        "all_routes": devhost_info.get("all_routes", {}),
    }


@app.get("/api/users")
async def get_users():
    """Example API endpoint"""
    return {"users": ["alice", "bob", "charlie"]}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "devhost": "enabled"}


if __name__ == "__main__":
    print("Starting FastAPI with Devhost middleware...")
    print("\nEndpoints:")
    print("  GET / - Root with subdomain info")
    print("  GET /api/users - Example API endpoint")
    print("  GET /health - Health check")
    print("\nConfigure routes with: devhost add <name> <port>")
    print("Then access at: http://<name>.localhost")
    
    uvicorn.run(app, host="127.0.0.1", port=8000)
