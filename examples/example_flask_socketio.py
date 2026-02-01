"""
Flask-SocketIO Example with Devhost (v2.3+)

This example demonstrates using Devhost with a Flask app that uses Flask-SocketIO
for WebSocket support. This is the recommended pattern for real-time Flask apps.

Usage:
    # Install dependencies
    pip install devhost[flask,yaml] flask-socketio

    # Optional: Create project config once
    devhost init
    # Answer: name=myapp, port=8000

    # Run the example
    python examples/example_flask_socketio.py

    # Access at:
    # http://myapp.localhost:8000

Key Concepts:
    - `name` parameter: The subdomain for your app (e.g., name="myapp" → http://myapp.localhost)
      * Can be ANYTHING you want - not tied to devhost.yml
      * If omitted, reads from devhost.yml or uses directory name
      * Examples: name="api", name="frontend", name="sysgrow"

    - `socketio` parameter: Pass your Flask-SocketIO instance for WebSocket support
      * Required for Flask apps using Flask-SocketIO
      * Uses socketio.run() instead of app.run()

    - Priority for name resolution:
      1. Explicit `name="myapp"` parameter (highest priority)
      2. `name` field in devhost.yml
      3. Current directory name (fallback)
"""

from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

from devhost_cli.frameworks import run_flask

# Create Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key"

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Simple HTML page with WebSocket support
INDEX_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Flask-SocketIO with Devhost</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.0/socket.io.js"></script>
</head>
<body>
    <h1>Flask-SocketIO with Devhost</h1>
    <p>WebSocket Status: <span id="status">Connecting...</span></p>
    <p>Message from server: <span id="message">Waiting...</span></p>
    <button onclick="sendPing()">Send Ping</button>
    <script>
        const socket = io();
        socket.on('connect', function() {
            document.getElementById('status').textContent = 'Connected ✓';
            document.getElementById('status').style.color = 'green';
        });
        socket.on('disconnect', function() {
            document.getElementById('status').textContent = 'Disconnected ✗';
            document.getElementById('status').style.color = 'red';
        });
        socket.on('pong', function(data) {
            document.getElementById('message').textContent = data.message;
        });
        function sendPing() {
            socket.emit('ping', {data: 'Hello from client!'});
        }
    </script>
</body>
</html>"""


@app.route("/")
def index():
    """Serve the main page"""
    return render_template_string(INDEX_HTML)


@app.route("/api/health")
def health():
    """Health check endpoint"""
    return {"status": "ok", "websocket": "enabled"}


@socketio.on("connect")
def handle_connect():
    """Handle WebSocket connection"""
    print("Client connected!")
    emit("pong", {"message": "Welcome! You are connected via WebSocket."})


@socketio.on("ping")
def handle_ping(data):
    """Handle ping messages"""
    print(f"Received ping: {data}")
    emit("pong", {"message": f"Pong! Received: {data.get('data', '')}"})


@socketio.on("disconnect")
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print("Client disconnected")


if __name__ == "__main__":
    # ============================================================
    # KEY: The `name` parameter can be ANYTHING you want!
    # ============================================================
    #
    # Examples:
    #   run_flask(app, name="myapp", socketio=socketio)     → http://myapp.localhost:8000
    #   run_flask(app, name="api", socketio=socketio)       → http://api.localhost:8000
    #   run_flask(app, name="frontend", socketio=socketio)  → http://frontend.localhost:8000
    #   run_flask(app, name="sysgrow", socketio=socketio)   → http://sysgrow.localhost:8000
    #
    # The name does NOT need to match devhost.yml - it overrides it!
    # If you omit name, it will use:
    #   1. The 'name' field from devhost.yml (if exists)
    #   2. The current directory name (fallback)
    #
    run_flask(
        app,
        name="socketio-demo",  # ← This becomes the subdomain
        socketio=socketio,  # ← Required for WebSocket support
        port=8000,  # ← Optional: auto-finds if not specified
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True,  # For development only
    )
