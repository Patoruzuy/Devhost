"""
Zero-Config FastAPI Example (v2.3+)

The simplest way to run a FastAPI app with Devhost subdomain support.
Just one line: runner.run(app) - that's it!

Usage:
    # Install devhost with YAML support
    pip install devhost[yaml]

    # Optional: Create project config
    devhost init
    # Answer: name=myapi, port=auto

    # Run the example
    python examples/example_zero_config_fastapi.py

    # Access at:
    # http://myapi.localhost:8000 (or port shown in console)

Features:
    - Auto-registers route on startup
    - Auto-cleanup on exit
    - Reads devhost.yml if present
    - Uses uvicorn for serving
"""

from fastapi import FastAPI

from devhost_cli.runner import run

# Create FastAPI app
app = FastAPI(title="Zero-Config FastAPI Example")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": "Zero-Config FastAPI Example",
        "message": "Running with devhost auto-registration!",
        "tip": "Check devhost list to see this route registered",
    }


@app.get("/api/users")
async def get_users():
    """Example API endpoint."""
    return {"users": ["alice", "bob", "charlie"]}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    # That's it! One line to run with subdomain support.
    # The app will:
    # 1. Find a free port (or use devhost.yml config)
    # 2. Register itself (e.g., myapi.localhost → 127.0.0.1:8000)
    # 3. Start uvicorn server
    # 4. Cleanup the route on exit
    run(app, name="myapi")
