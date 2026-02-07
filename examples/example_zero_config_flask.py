"""
Zero-Config Flask Example (v2.3+)

The simplest way to run a Flask app with Devhost subdomain support.
Just one line: runner.run(app) - that's it!

Usage:
    # Install devhost with Flask and YAML support
    pip install devhost[flask,yaml]

    # Optional: Create project config
    devhost init
    # Answer: name=myflask, port=auto

    # Run the example
    python examples/example_zero_config_flask.py

    # Access at:
    # http://myflask.localhost:8000 (or port shown in console)

Features:
    - Auto-registers route on startup
    - Auto-cleanup on exit
    - Reads devhost.yml if present
    - Detects Flask-SocketIO automatically
"""

from flask import Flask, jsonify

from devhost_cli.runner import run

# Create Flask app
app = Flask(__name__)


@app.route("/")
def index():
    """Root endpoint."""
    return jsonify(
        {
            "app": "Zero-Config Flask Example",
            "message": "Running with devhost auto-registration!",
            "tip": "Check devhost list to see this route registered",
        }
    )


@app.route("/api/users")
def users():
    """Example API endpoint."""
    return jsonify({"users": ["alice", "bob", "charlie"]})


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # That's it! One line to run with subdomain support.
    # The app will:
    # 1. Find a free port (or use devhost.yml config)
    # 2. Register itself (e.g., myflask.localhost → 127.0.0.1:8000)
    # 3. Start the Flask development server
    # 4. Cleanup the route on exit
    run(app, name="myflask")
