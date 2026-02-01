"""
Backward-compatible entry point for router/app.py.
Imports and runs the refactored router from devhost_cli.router.
"""

import sys
from pathlib import Path

# Add parent directory to path to import devhost_cli
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn

from devhost_cli.router import create_app

app = create_app()


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5555, reload=True)
