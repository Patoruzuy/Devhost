"""
Zero-Config Generic Runner Example (v2.3+)

Use the generic runner with any WSGI/ASGI app or framework.
Automatically detects Flask, FastAPI, Django, or runs as generic WSGI.

Usage:
    # Install devhost with YAML support
    pip install devhost[yaml]

    # Create devhost.yml (optional but recommended)
    devhost init
    # Answer: name=myapp, port=auto

    # Run the example
    python examples/example_zero_config_generic.py

    # Access at:
    # http://myapp.localhost:8000 (or port shown in console)

Features:
    - Auto-detects framework (Flask, FastAPI, Django)
    - Auto-registers route on startup
    - Auto-cleanup on exit
    - Reads devhost.yml if present
"""

from flask import Flask, jsonify

from devhost_cli.runner import run

# Create Flask app (could be FastAPI or any WSGI app)
app = Flask(__name__)


@app.route("/")
def index():
    """Root endpoint."""
    return jsonify(
        {
            "app": "Generic Runner Example",
            "message": "Framework auto-detected!",
            "framework": "Flask (auto-detected)",
        }
    )


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # The generic run() function auto-detects your framework:
    # - Flask → uses Flask development server
    # - FastAPI → uses uvicorn
    # - Django → uses Django runserver
    # - Other → uses waitress or gunicorn
    run(app, name="myapp")
