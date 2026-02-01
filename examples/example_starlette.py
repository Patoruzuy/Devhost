"""
Starlette integration example with Devhost.

This demonstrates using Devhost middleware with Starlette applications.

Usage:
    pip install devhost starlette
    python examples/example_starlette.py
"""

import uvicorn
from devhost import DevhostMiddleware
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


async def homepage(request):
    """Homepage with subdomain info"""
    devhost_info = request.scope.get("devhost", {})
    subdomain = devhost_info.get("subdomain")
    target = devhost_info.get("target")

    return JSONResponse(
        {
            "app": "Starlette + Devhost",
            "subdomain": subdomain,
            "target": target,
        }
    )


async def health(request):
    """Health check endpoint"""
    return JSONResponse({"status": "ok"})


app = Starlette(
    debug=True,
    routes=[
        Route("/", homepage),
        Route("/health", health),
    ],
)

# Add Devhost middleware
app.add_middleware(DevhostMiddleware)


if __name__ == "__main__":
    print("Starting Starlette app with Devhost...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
