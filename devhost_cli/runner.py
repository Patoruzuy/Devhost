"""
Unified application runner for Devhost.

Provides a single entry point to run Flask, Django, FastAPI, or any WSGI/ASGI app
with automatic route registration and subdomain support.
"""

import atexit
import signal
import socket
import sys
from typing import Any

from .config import Config, ProjectConfig
from .state import StateConfig
from .utils import msg_error, msg_info, msg_success, msg_warning


def find_free_port(start: int = 8000, end: int = 9000) -> int:
    """Find an available port in the given range"""
    for port in range(start, end):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No free ports found in range {start}-{end}")


def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            return False
    except OSError:
        return True


class DevhostRunner:
    """
    Manages app lifecycle with automatic route registration.

    Usage:
        from devhost_cli.runner import run

        # Flask
        run(app)

        # With explicit name
        run(app, name="myapi", port=8000)
    """

    def __init__(
        self,
        app: Any,
        name: str | None = None,
        port: int | None = None,
        domain: str | None = None,
        host: str = "127.0.0.1",
        auto_register: bool = True,
        auto_caddy: bool = True,
        **kwargs,
    ):
        self.app = app
        self.host = host
        self.kwargs = kwargs
        self.registered_name: str | None = None
        self.registered_port: int | None = None

        # Load project config
        self.project_config = ProjectConfig()

        # Override with explicit params or use project config
        self.name = name or self.project_config.name
        self.port = port or self.project_config.port or find_free_port()
        self.domain = domain or self.project_config.domain
        self.auto_register = auto_register if auto_register is not None else self.project_config.auto_register
        self.auto_caddy = auto_caddy if auto_caddy is not None else self.project_config.auto_caddy

        # Global config for route registration
        self.global_config = Config()

        # Detect framework
        self.framework = self._detect_framework()

    def _detect_framework(self) -> str:
        """Detect which framework the app is using"""
        app_type = type(self.app).__name__
        app_module = type(self.app).__module__

        if "flask" in app_module.lower() or app_type == "Flask":
            return "flask"
        elif "django" in app_module.lower():
            return "django"
        elif "fastapi" in app_module.lower() or app_type == "FastAPI":
            return "fastapi"
        elif "starlette" in app_module.lower() or app_type == "Starlette":
            return "starlette"
        else:
            # Check if it's a WSGI callable
            if callable(self.app):
                return "wsgi"
            return "unknown"

    def _resolve_name_conflict(self, name: str, port: int) -> str:
        """
        Check if name already exists with different port.
        Prompt user to confirm or use name-2 suffix.
        """
        routes = self.global_config.load()

        if name not in routes:
            return name

        existing_target = routes[name]

        # Parse existing port
        existing_port = None
        if isinstance(existing_target, int):
            existing_port = existing_target
        elif isinstance(existing_target, str):
            if existing_target.isdigit():
                existing_port = int(existing_target)
            elif ":" in existing_target:
                try:
                    existing_port = int(existing_target.split(":")[-1].split("/")[0])
                except ValueError:
                    pass

        # Same port - no conflict
        if existing_port == port:
            return name

        # Different port - conflict!
        msg_warning(f"'{name}' already registered on port {existing_port}")

        # Check if running interactively
        if sys.stdin.isatty():
            # Find next available suffix
            suffix = 2
            new_name = f"{name}-{suffix}"
            while new_name in routes:
                suffix += 1
                new_name = f"{name}-{suffix}"

            try:
                response = input(f"Use '{new_name}' instead? [Y/n]: ").strip().lower()
                if response in ("", "y", "yes"):
                    msg_info(f"Using '{new_name}' instead")
                    return new_name
                elif response in ("n", "no"):
                    msg_info(f"Overwriting '{name}' with new port {port}")
                    return name
            except (EOFError, KeyboardInterrupt):
                print()
                return name
        else:
            # Non-interactive: auto-suffix
            suffix = 2
            new_name = f"{name}-{suffix}"
            while new_name in routes:
                suffix += 1
                new_name = f"{name}-{suffix}"
            msg_info(f"Auto-assigned name: {new_name}")
            return new_name

    def register(self):
        """Register route in global devhost.json"""
        if not self.auto_register:
            return

        # Resolve any name conflicts
        resolved_name = self._resolve_name_conflict(self.name, self.port)

        routes = self.global_config.load()
        routes[resolved_name] = self.port
        self.global_config.save(routes)

        self.registered_name = resolved_name
        self.registered_port = self.port

        msg_success(f"Registered: {resolved_name}.{self.domain} -> 127.0.0.1:{self.port}")
        try:
            upstream = f"{self.host}:{self.port}"
            StateConfig().set_route(resolved_name, upstream=upstream, domain=self.domain, enabled=True)
        except Exception:
            pass

    def unregister(self):
        """Remove route from global devhost.json on exit"""
        if not self.registered_name:
            return

        try:
            routes = self.global_config.load()
            if self.registered_name in routes:
                # Only remove if it still points to our port
                target = routes[self.registered_name]
                if target == self.registered_port or str(target) == str(self.registered_port):
                    del routes[self.registered_name]
                    self.global_config.save(routes)
                    msg_info(f"Unregistered: {self.registered_name}")
                    try:
                        StateConfig().remove_route(self.registered_name)
                    except Exception:
                        pass
        except Exception:
            pass  # Best effort cleanup

    def _check_caddy(self):
        """Check and optionally start Caddy for port 80 access"""
        if not self.auto_caddy:
            return
        try:
            if StateConfig().proxy_mode != "system":
                return
        except Exception:
            pass

        # Check if Caddy is needed (port 80 access)
        if not is_port_in_use(80):
            # Port 80 is free - try to start Caddy
            try:
                from .caddy import caddy_start, is_caddy_running

                if not is_caddy_running():
                    if sys.stdin.isatty():
                        response = input("Start Caddy for http://name.localhost access? [Y/n]: ").strip().lower()
                        if response in ("", "y", "yes"):
                            caddy_start()
                            msg_success("Caddy started on port 80")
            except Exception:
                pass  # Caddy not available
        else:
            # Port 80 in use - just inform user
            msg_info(f"Port 80 in use. Access at: http://{self.registered_name or self.name}.{self.domain}:{self.port}")

    def _print_startup_info(self):
        """Print startup information"""
        name = self.registered_name or self.name
        mode = "gateway"
        gateway_port = 7777
        try:
            state = StateConfig()
            mode = state.proxy_mode
            gateway_port = state.gateway_port
        except Exception:
            pass

        if mode == "gateway":
            url = f"http://{name}.{self.domain}:{gateway_port}"
        elif mode in ("system", "external"):
            url = f"http://{name}.{self.domain}"
        else:
            url = f"http://{self.host}:{self.port}"

        print()
        print(f"🚀 Starting {name}...")
        print(f"   Framework: {self.framework}")
        print(f"   Port: {self.port}")
        print()

        print(f"🌐 Access at: {url}")

        print()

    def _ensure_gateway_router(self):
        """Start the gateway router when running in gateway mode."""
        try:
            state = StateConfig()
            if state.proxy_mode != "gateway":
                return
        except Exception:
            return

        try:
            from .router_manager import Router

            router = Router()
            if not router.is_running()[0]:
                msg_info("Starting Devhost gateway router...")
                router.start()
        except Exception:
            pass

    def _run_flask(self):
        """Run Flask application"""
        # Check for Flask-SocketIO
        socketio = self.kwargs.pop("socketio", None)

        if socketio:
            # Use socketio.run for WebSocket support
            socketio.run(
                self.app,
                host=self.host,
                port=self.port,
                debug=self.kwargs.get("debug", False),
                use_reloader=self.kwargs.get("use_reloader", False),
                allow_unsafe_werkzeug=self.kwargs.get("allow_unsafe_werkzeug", True),
                **{k: v for k, v in self.kwargs.items() if k not in ("debug", "use_reloader", "allow_unsafe_werkzeug")},
            )
        else:
            self.app.run(
                host=self.host,
                port=self.port,
                debug=self.kwargs.get("debug", False),
                use_reloader=self.kwargs.get("use_reloader", False),
                **{k: v for k, v in self.kwargs.items() if k not in ("debug", "use_reloader")},
            )

    def _run_fastapi(self):
        """Run FastAPI application with uvicorn"""
        try:
            import uvicorn

            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                reload=self.kwargs.get("reload", False),
                log_level=self.kwargs.get("log_level", "info"),
            )
        except ImportError:
            msg_error("uvicorn not installed. Run: pip install uvicorn")
            sys.exit(1)

    def _run_django(self):
        """Run Django application"""
        # Django uses management commands, so we just call runserver
        from django.core.management import execute_from_command_line

        sys.argv = ["manage.py", "runserver", f"{self.host}:{self.port}", "--noreload"]
        execute_from_command_line(sys.argv)

    def _run_wsgi(self):
        """Run generic WSGI application with waitress or werkzeug"""
        try:
            from waitress import serve

            serve(self.app, host=self.host, port=self.port)
        except ImportError:
            try:
                from werkzeug.serving import run_simple

                run_simple(self.host, self.port, self.app, use_reloader=False)
            except ImportError:
                msg_error("No WSGI server available. Install waitress or werkzeug.")
                sys.exit(1)

    def run(self):
        """Run the application with automatic registration"""

        # Setup signal handlers for cleanup
        def cleanup_handler(signum, frame):
            self.unregister()
            sys.exit(0)

        signal.signal(signal.SIGINT, cleanup_handler)
        signal.signal(signal.SIGTERM, cleanup_handler)

        # Register cleanup on normal exit
        atexit.register(self.unregister)

        # Register route
        self.register()

        # Ensure proxy is running (gateway mode)
        self._ensure_gateway_router()

        # Check/start Caddy
        self._check_caddy()

        # Print startup info
        self._print_startup_info()

        # Run framework-specific server
        try:
            if self.framework == "flask":
                self._run_flask()
            elif self.framework == "fastapi":
                self._run_fastapi()
            elif self.framework == "starlette":
                self._run_fastapi()  # Also uses uvicorn
            elif self.framework == "django":
                self._run_django()
            else:
                self._run_wsgi()
        finally:
            self.unregister()


def run(
    app: Any,
    name: str | None = None,
    port: int | None = None,
    domain: str | None = None,
    host: str = "127.0.0.1",
    auto_register: bool = True,
    auto_caddy: bool = True,
    **kwargs,
):
    """
    Run any web application with automatic Devhost registration.

    Args:
        app: Flask, FastAPI, Django, or WSGI application
        name: App name (becomes subdomain). Auto-detected from devhost.yml or directory
        port: Port to run on. Auto-detected if not specified
        domain: Base domain (default: localhost)
        host: Host to bind to (default: 127.0.0.1 for security)
        auto_register: Register route in devhost.json (default: True)
        auto_caddy: Prompt to start Caddy for port 80 (default: True)
        **kwargs: Additional arguments passed to the framework's run method

    Example:
        from flask import Flask
        from devhost_cli.runner import run

        app = Flask(__name__)

        @app.route('/')
        def index():
            return "Hello!"

        if __name__ == '__main__':
            run(app)  # Accessible at http://myproject.localhost
    """
    runner = DevhostRunner(
        app=app,
        name=name,
        port=port,
        domain=domain,
        host=host,
        auto_register=auto_register,
        auto_caddy=auto_caddy,
        **kwargs,
    )
    runner.run()
