"""
Standalone proxy server example using Devhost.

This creates a reverse proxy that routes requests based on subdomain
to local development services configured in devhost.json.

Usage:
    pip install devhost
    python examples/example_proxy.py

Configure routes:
    devhost add hello 3000
    devhost add api 8080

Then access:
    - http://hello.localhost:5555/ -> http://127.0.0.1:3000/
    - http://api.localhost:5555/ -> http://127.0.0.1:8080/
"""

import uvicorn
from devhost import create_devhost_app

if __name__ == "__main__":
    print("Starting Devhost proxy server...")
    print("\nManage routes:")
    print("  devhost add <name> <port>")
    print("  devhost list")
    print("\nEndpoints:")
    print("  http://127.0.0.1:5555/health  - Health check")
    print("  http://127.0.0.1:5555/routes  - List routes")
    print("  http://127.0.0.1:5555/metrics - Request metrics")

    app = create_devhost_app()
    uvicorn.run(app, host="127.0.0.1", port=5555)
