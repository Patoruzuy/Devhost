"""
FastAPI integration example with Devhost.

This demonstrates how to use Devhost middleware in a FastAPI application
to enable subdomain-based routing.

Usage:
    pip install devhost
    python examples/example_fastapi.py

Then access:
    - http://hello.localhost:8000/ (if "hello" route exists in devhost.json)
    - http://localhost:8000/ (no subdomain)
"""

import uvicorn
from devhost import enable_subdomain_routing
from fastapi import FastAPI, Request

app = FastAPI(title="Devhost FastAPI Example")

# Enable subdomain routing
enable_subdomain_routing(app)


@app.get("/")
async def read_root(request: Request):
    """Homepage that shows current subdomain and target info"""
    devhost_info = request.scope.get("devhost", {})
    subdomain = devhost_info.get("subdomain")
    target = devhost_info.get("target")
    domain = devhost_info.get("domain", "localhost")

    return {
        "message": f"Hello from {subdomain or 'main'}!",
        "subdomain": subdomain,
        "domain": domain,
        "target": target,
        "note": "Add routes with: devhost add <name> <port>",
    }


@app.get("/info")
async def get_info(request: Request):
    """Show detailed request information"""
    devhost_info = request.scope.get("devhost", {})

    return {
        "path": request.url.path,
        "method": request.method,
        "headers": dict(request.headers),
        "devhost": devhost_info,
    }


if __name__ == "__main__":
    print("Starting FastAPI app with Devhost subdomain routing...")
    print("Add routes: devhost add hello 3000")
    print("Then visit: http://hello.localhost:8000/")
    uvicorn.run(app, host="127.0.0.1", port=8000)
