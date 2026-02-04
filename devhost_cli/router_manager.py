"""Router process lifecycle management"""

import os
import signal
import subprocess
import time
from pathlib import Path

from .platform import IS_WINDOWS, find_python
from .utils import msg_error, msg_info, msg_step, msg_success, msg_warning


def is_pip_installed() -> bool:
    """Check if devhost was installed via pip (no router directory)"""
    script_dir = Path(__file__).parent.parent.resolve()
    router_dir = script_dir / "router"
    return not router_dir.exists()


class Router:
    """Manages router process lifecycle"""

    def __init__(self):
        self.script_dir = Path(__file__).parent.parent.resolve()
        self.router_dir = self.script_dir / "router"
        # Use user's home directory for PID file (works for pip install)
        self.devhost_dir = Path.home() / ".devhost"
        self.pid_file = self.devhost_dir / "router.pid"
        if IS_WINDOWS:
            temp = os.environ.get("TEMP", ".")
            self.log_file = Path(temp) / "devhost-router.log"
            self.err_file = Path(temp) / "devhost-router.err.log"
        else:
            self.log_file = Path("/tmp/devhost-router.log")
            self.err_file = Path("/tmp/devhost-router.err.log")

    def is_running(self) -> tuple[bool, int | None]:
        """Check if router is running, return (is_running, pid)"""
        if not self.pid_file.exists():
            # Fallback: check if router port is responding
            if self._check_health():
                return (True, None)
            return (False, None)

        try:
            pid = int(self.pid_file.read_text().strip())

            # Check if process is alive
            try:
                os.kill(pid, 0)  # Signal 0 just checks if process exists
                return (True, pid)
            except (OSError, ProcessLookupError):
                # Stale PID file
                self.pid_file.unlink(missing_ok=True)
                return (False, None)
        except (OSError, ValueError):
            return (False, None)

    def _check_health(self) -> bool:
        """Check if router is responding"""
        try:
            import urllib.request

            req = urllib.request.Request("http://127.0.0.1:7777/health")
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    def start(self) -> bool:
        """Start the router process"""
        # Check if installed via pip (no router directory)
        if is_pip_installed():
            msg_warning("Router not available when installed via pip.")
            msg_info("")
            msg_info("With pip install, the router is not needed!")
            msg_info("Caddy proxies directly to your app.")
            msg_info("")
            msg_info("Usage:")
            msg_info("  1. Add your route:    devhost add myapp 8000")
            msg_info("  2. Start Caddy:       devhost caddy start")
            msg_info("  3. Run your app on port 8000")
            msg_info("  4. Access at:         http://myapp.localhost")
            msg_info("")
            msg_info("Or use the zero-config runner:")
            msg_info("  from devhost_cli.frameworks import run_flask")
            msg_info("  run_flask(app, name='myapp')")
            return False

        msg_step(1, 3, "Checking if router is already running...")
        running, pid = self.is_running()
        if running:
            msg_warning(f"Router already running{f' (pid {pid})' if pid else ''}")
            return True

        if IS_WINDOWS:
            from .windows import caddy_start

            caddy_start()

        msg_step(2, 3, "Finding Python interpreter...")
        python = find_python()
        if not python:
            msg_error("Python not found. Please install Python 3.10+")
            return False

        msg_info(f"Using: {python}")

        if IS_WINDOWS:
            venv_cfg = self.router_dir / "venv" / "pyvenv.cfg"
            if venv_cfg.exists():
                for line in venv_cfg.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("home = "):
                        home = line.replace("home = ", "").strip()
                        if not home.startswith(tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")):
                            msg_error("Venv appears to be created by WSL. Recreate with Python installer.")
                            return False

        # Check if uvicorn is installed
        result = subprocess.run([str(python), "-c", "import uvicorn"], capture_output=True)
        if result.returncode != 0:
            msg_warning("uvicorn not found in venv, installing dependencies...")
            req_file = self.router_dir / "requirements.txt"
            if req_file.exists():
                subprocess.run([str(python), "-m", "pip", "install", "-q", "-r", str(req_file)])

        msg_step(3, 3, "Starting router...")

        # Ensure directories exist
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.err_file.parent.mkdir(parents=True, exist_ok=True)

        # Start router process
        cmd = [
            str(python),
            "-m",
            "uvicorn",
            "app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "7777",
        ]

        creationflags = 0
        if IS_WINDOWS and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

        with open(self.log_file, "a", encoding="utf-8") as log, open(self.err_file, "a", encoding="utf-8") as err:
            process = subprocess.Popen(
                cmd,
                cwd=str(self.router_dir),
                stdout=log,
                stderr=err,
                start_new_session=not IS_WINDOWS,
                creationflags=creationflags,
            )

        # Save PID
        self.pid_file.write_text(str(process.pid))

        # Wait a moment and check if it started
        time.sleep(1)
        if not self.is_running()[0]:
            msg_error("Router failed to start")
            msg_info(f"Check logs: {self.log_file}")
            return False

        msg_success(f"Router started (pid {process.pid})")
        msg_info(f"Logs: {self.log_file}")
        msg_info(f"Errors: {self.err_file}")
        return True

    def stop(self) -> bool:
        """Stop the router process"""
        running, pid = self.is_running()
        if not running:
            msg_info("Router is not running")
            return True

        if pid:
            try:
                os.kill(pid, signal.SIGTERM if not IS_WINDOWS else signal.SIGBREAK)
                msg_success(f"Sent stop signal to process {pid}")

                # Wait for process to stop
                for _ in range(5):
                    time.sleep(0.5)
                    if not self.is_running()[0]:
                        break

                # Force kill if still running
                if self.is_running()[0]:
                    os.kill(pid, signal.SIGKILL if not IS_WINDOWS else signal.SIGBREAK)
                    msg_warning("Forced process termination")

                self.pid_file.unlink(missing_ok=True)
                msg_success("Router stopped")
                return True
            except Exception as e:
                msg_error(f"Failed to stop router: {e}")
                return False
        else:
            msg_warning("Router running but PID unknown - cannot stop")
            return False

    def status(self, json_output: bool = False) -> bool:
        """Show router status"""
        running, pid = self.is_running()
        health = self._check_health()

        if json_output:
            import json

            print(json.dumps({"running": running, "pid": pid, "health": "ok" if health else "not_responding"}))
            return running

        if running:
            msg_success(f"Router running{f' (pid {pid})' if pid else ''}")
            if health:
                msg_success("Health check: OK")
            else:
                msg_error("Health check: not responding")
        else:
            msg_info("Router not running")

        return running
