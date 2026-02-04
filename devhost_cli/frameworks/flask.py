"""
Flask wrapper for Devhost runner.

Provides simplified API for running Flask apps with Devhost.
"""

from typing import Any

from ..runner import run as devhost_run


def run_flask(
    app: Any,
    name: str | None = None,
    port: int | None = None,
    domain: str = "localhost",
    host: str = "127.0.0.1",
    debug: bool = False,
    use_reloader: bool = False,
    socketio: Any | None = None,
    **kwargs,
):
    """
    Run a Flask application with automatic Devhost registration.

    Args:
        app: Flask application instance
        name: App name (becomes subdomain). Auto-detected from devhost.yml or directory
        port: Port to run on. Auto-detected if not specified
        domain: Base domain (default: localhost)
        host: Host to bind to (default: 127.0.0.1 for security)
        debug: Enable Flask debug mode (default: False)
        use_reloader: Enable auto-reload on code changes (default: False)
        socketio: Flask-SocketIO instance for WebSocket support
        **kwargs: Additional arguments passed to app.run() or socketio.run()

    Example:
        from flask import Flask
        from devhost_cli.frameworks.flask import run_flask

        app = Flask(__name__)

        @app.route('/')
        def index():
            return "Hello!"

        if __name__ == '__main__':
            run_flask(app)  # Accessible at http://myproject.localhost

    With SocketIO:
        from flask import Flask
        from flask_socketio import SocketIO
        from devhost_cli.frameworks.flask import run_flask

        app = Flask(__name__)
        socketio = SocketIO(app)

        if __name__ == '__main__':
            run_flask(app, socketio=socketio)
    """
    devhost_run(
        app=app,
        name=name,
        port=port,
        domain=domain,
        host=host,
        debug=debug,
        use_reloader=use_reloader,
        socketio=socketio,
        **kwargs,
    )
