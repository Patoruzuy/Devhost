"""
Caddy lifecycle management for Devhost v3.0 Mode 2 (System Proxy)

Implements the ownership model:
- Devhost owns the Caddy process when in Mode 2
- Smart stop logic: only stop when no routes are active
- Port 80/443 conflict detection with best-next-action guidance
- PID tracking in state.yml
"""

import shutil
import subprocess
import time
from pathlib import Path
from typing import Literal

from .output import console, print_error, print_info, print_success, print_warning
from .platform import IS_WINDOWS
from .state import StateConfig

# Port conflict detection patterns
PORT_CONFLICT_HANDLERS: dict[str, str] = {
    "wslrelay": "Run 'wsl --shutdown' to free port 80 (WSL is using it)",
    "httpd": "Stop Apache: 'sudo systemctl stop apache2' or 'sudo apachectl stop'",
    "apache2": "Stop Apache: 'sudo systemctl stop apache2' or 'sudo apachectl stop'",
    "nginx": "Stop nginx: 'sudo systemctl stop nginx' or 'sudo nginx -s stop'",
    "iisexpress": "Stop IIS Express from system tray or Task Manager",
    "w3wp": "Stop IIS: Run 'iisreset /stop' from elevated prompt",
    "caddy": "Caddy is already running. Use 'devhost proxy stop' first.",
    "python": "A Python process is using port 80. Check for running dev servers.",
    "node": "A Node.js process is using port 80. Check for running dev servers.",
}


def find_caddy_executable() -> str | None:
    """Find Caddy executable on the system."""
    # Check PATH first
    cmd = shutil.which("caddy")
    if cmd:
        return cmd

    # Windows-specific: check WinGet packages
    if IS_WINDOWS:
        import os

        base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
        if base.exists():
            for path in base.glob("CaddyServer.Caddy*\\caddy.exe"):
                return str(path)

        # Check common Windows install locations
        common_paths = [
            Path("C:/Program Files/Caddy/caddy.exe"),
            Path("C:/Caddy/caddy.exe"),
        ]
        for path in common_paths:
            if path.exists():
                return str(path)
    else:
        # Unix-like: check common locations
        common_paths = [
            Path("/usr/local/bin/caddy"),
            Path("/usr/bin/caddy"),
            Path.home() / ".local" / "bin" / "caddy",
        ]
        for path in common_paths:
            if path.exists():
                return str(path)

    return None


def get_port_owner(port: int = 80) -> tuple[str | None, int | None]:
    """
    Get the process name and PID using a specific port.

    Returns (process_name, pid) or (None, None) if port is free.
    """
    if IS_WINDOWS:
        return _get_port_owner_windows(port)
    return _get_port_owner_unix(port)


def _get_port_owner_windows(port: int) -> tuple[str | None, int | None]:
    """Get port owner on Windows using PowerShell."""
    import json

    ps_cmd = f"""
    $conn = Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {{
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        @{{ pid = $conn.OwningProcess; name = $proc.ProcessName }} | ConvertTo-Json
    }}
    """
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        check=False,
    )

    if not result.stdout.strip():
        return (None, None)

    try:
        data = json.loads(result.stdout)
        return (data.get("name"), data.get("pid"))
    except (json.JSONDecodeError, KeyError):
        return (None, None)


def _get_port_owner_unix(port: int) -> tuple[str | None, int | None]:
    """Get port owner on Unix-like systems using lsof or ss."""
    # Try lsof first
    if shutil.which("lsof"):
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-t", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip():
            try:
                pid = int(result.stdout.strip().split()[0])
                # Get process name
                ps_result = subprocess.run(
                    ["ps", "-p", str(pid), "-o", "comm="],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                name = ps_result.stdout.strip() if ps_result.stdout.strip() else None
                return (name, pid)
            except (ValueError, IndexError):
                pass

    # Fallback to ss
    if shutil.which("ss"):
        result = subprocess.run(
            ["ss", "-tlnp", f"sport = :{port}"],
            capture_output=True,
            text=True,
            check=False,
        )
        # Parse ss output - it's complex, just check if there's output
        if result.stdout.strip() and "LISTEN" in result.stdout:
            return ("unknown", None)

    return (None, None)


def check_port_conflicts(ports: list[int] | None = None) -> list[dict]:
    """
    Check for port conflicts on the specified ports.

    Returns list of conflicts with best-next-action guidance.
    """
    if ports is None:
        ports = [80, 443]

    conflicts = []
    for port in ports:
        name, pid = get_port_owner(port)
        if name:
            handler = PORT_CONFLICT_HANDLERS.get(name.lower(), f"Stop the process using port {port}")
            conflicts.append(
                {
                    "port": port,
                    "process": name,
                    "pid": pid,
                    "action": handler,
                }
            )

    return conflicts


def print_port_conflicts(conflicts: list[dict]) -> None:
    """Print port conflicts with best-next-action guidance."""
    if not conflicts:
        print_success("Ports 80 and 443 are available")
        return

    print_error("Port conflicts detected:")
    for conflict in conflicts:
        console.print(f"  Port {conflict['port']}: [yellow]{conflict['process']}[/yellow]", end="")
        if conflict["pid"]:
            console.print(f" (PID {conflict['pid']})")
        else:
            console.print()
        console.print(f"    [dim]{conflict['action']}[/dim]")


def generate_system_caddyfile(state: StateConfig) -> str:
    """Generate Caddyfile for Mode 2 (system proxy)."""
    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    domain = state.system_domain
    routes = state.routes
    active_routes = {name: r for name, r in routes.items() if r.get("enabled", True)}
    listen_http = state.raw.get("proxy", {}).get("system", {}).get("listen_http", "127.0.0.1:80")
    listen_https = state.raw.get("proxy", {}).get("system", {}).get("listen_https", "127.0.0.1:443")

    def _split_listen(value: str, default_host: str, default_port: int) -> tuple[str, int]:
        if not value:
            return (default_host, default_port)
        if ":" in value:
            host, port_str = value.rsplit(":", 1)
            try:
                return (host or default_host, int(port_str))
            except ValueError:
                return (host or default_host, default_port)
        return (value, default_port)

    http_host, http_port = _split_listen(listen_http, "127.0.0.1", 80)
    https_host, https_port = _split_listen(listen_https, "127.0.0.1", 443)

    lines = [
        "# Auto-generated by Devhost Mode 2 (System Proxy)",
        f"# Last updated: {timestamp}",
        f"# Routes: {len(active_routes)} active",
        "",
        "# Global options",
        "{",
        f"    # Expected HTTP listen: {listen_http}",
        f"    # Expected HTTPS listen: {listen_https}",
        "    # admin off",
        "}",
        "",
    ]

    for name, route in sorted(active_routes.items()):
        upstream = route.get("upstream", "127.0.0.1:8000")
        route_domain = route.get("domain", domain)
        host = f"{name}.{route_domain}"

        # Ensure upstream uses 127.0.0.1 format
        if not upstream.startswith("http"):
            upstream = f"http://{upstream}"

        lines.extend(
            [
                f"http://{host}:{http_port} {{",
                f"    bind {http_host}",
                f"    reverse_proxy {upstream}",
                "}",
                "",
            ]
        )

    return "\n".join(lines)


def get_caddyfile_path(state: StateConfig) -> Path:
    """Get the Caddyfile path for Mode 2."""
    return state.devhost_dir / "proxy" / "caddy" / "Caddyfile"


def write_system_caddyfile(state: StateConfig) -> Path:
    """Write the system Caddyfile for Mode 2."""
    content = generate_system_caddyfile(state)
    caddyfile = get_caddyfile_path(state)
    caddyfile.parent.mkdir(parents=True, exist_ok=True)
    caddyfile.write_text(content, encoding="utf-8")

    # Record hash for integrity
    state.record_hash(caddyfile)

    return caddyfile


def should_stop_caddy(state: StateConfig) -> bool:
    """
    Determine if Caddy should be stopped.

    Returns True if:
    - No routes exist
    - All routes are disabled
    """
    routes = state.routes
    if len(routes) == 0:
        return True
    if all(not route.get("enabled", True) for route in routes.values()):
        return True
    return False


def is_caddy_running(state: StateConfig) -> bool:
    """Check if our owned Caddy process is running."""
    pid = state.raw.get("proxy", {}).get("system", {}).get("caddy_pid")
    if not pid:
        return False

    if IS_WINDOWS:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Get-Process -Id {pid} -ErrorAction SilentlyContinue"],
            capture_output=True,
            text=True,
            check=False,
        )
        return bool(result.stdout.strip())
    else:
        # Unix: check if process exists
        try:
            import os

            os.kill(pid, 0)
            return True
        except OSError:
            return False


def get_caddy_pid() -> int | None:
    """Get PID of any running Caddy process."""
    if IS_WINDOWS:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "(Get-Process caddy -ErrorAction SilentlyContinue).Id"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip():
            try:
                return int(result.stdout.strip())
            except ValueError:
                pass
    else:
        result = subprocess.run(
            ["pgrep", "-x", "caddy"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip():
            try:
                return int(result.stdout.strip().split()[0])
            except (ValueError, IndexError):
                pass

    return None


def _save_caddy_pid(state: StateConfig, pid: int | None) -> None:
    """Save Caddy PID to state."""
    state._state.setdefault("proxy", {}).setdefault("system", {})["caddy_pid"] = pid
    state._save()


def start_caddy(state: StateConfig, force: bool = False) -> tuple[bool, str]:
    """
    Start Caddy for Mode 2 (system proxy).

    Returns (success, message).
    """
    # Check if already running
    if is_caddy_running(state) and not force:
        return (True, "Caddy is already running")

    # Find Caddy executable
    caddy_exe = find_caddy_executable()
    if not caddy_exe:
        return (False, "Caddy not found. Install with: devhost install --caddy")

    # Check port conflicts
    conflicts = check_port_conflicts([80, 443])
    if conflicts:
        # Check if it's our Caddy
        stored_pid = state.raw.get("proxy", {}).get("system", {}).get("caddy_pid")
        for c in conflicts:
            if c["process"].lower() == "caddy":
                existing_pid = c["pid"]
                if existing_pid and stored_pid and existing_pid == stored_pid:
                    return (True, f"Caddy already running (PID {existing_pid})")
                # Caddy is running but not owned by Devhost
                return (
                    False,
                    "Caddy is already running but is not managed by Devhost. Stop it or switch to external mode.",
                )

        # Other process blocking
        print_port_conflicts(conflicts)
        return (False, "Port conflicts prevent Caddy from starting")

    # Generate Caddyfile
    caddyfile = write_system_caddyfile(state)

    # Start Caddy
    if IS_WINDOWS:
        # Windows: use 'caddy start' for background process
        result = subprocess.run(
            [caddy_exe, "start", "--config", str(caddyfile)],
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        # Unix: use 'caddy start' for background process
        result = subprocess.run(
            [caddy_exe, "start", "--config", str(caddyfile)],
            capture_output=True,
            text=True,
            check=False,
        )

    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
        return (False, f"Failed to start Caddy: {error_msg}")

    # Wait a moment for process to start, then get PID
    time.sleep(0.5)
    pid = get_caddy_pid()
    _save_caddy_pid(state, pid)

    return (True, f"Caddy started (PID {pid})" if pid else "Caddy started")


def stop_caddy(state: StateConfig, force: bool = False) -> tuple[bool, str]:
    """
    Stop Caddy for Mode 2 (system proxy).

    Returns (success, message).
    """
    # Check if we should stop
    if not force and not should_stop_caddy(state):
        return (False, "Active routes exist. Use --force to stop anyway.")

    caddy_exe = find_caddy_executable()
    if not caddy_exe:
        return (False, "Caddy not found")

    # Check if running
    pid = get_caddy_pid()
    if not pid:
        _save_caddy_pid(state, None)
        return (True, "Caddy is not running")

    # Stop Caddy
    result = subprocess.run(
        [caddy_exe, "stop"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
        return (False, f"Failed to stop Caddy: {error_msg}")

    _save_caddy_pid(state, None)
    return (True, "Caddy stopped")


def reload_caddy(state: StateConfig) -> tuple[bool, str]:
    """
    Reload Caddy configuration.

    Returns (success, message).
    """
    caddy_exe = find_caddy_executable()
    if not caddy_exe:
        return (False, "Caddy not found")

    if not is_caddy_running(state) and not get_caddy_pid():
        return (False, "Caddy is not running. Use 'devhost proxy start' first.")

    # Regenerate Caddyfile
    caddyfile = write_system_caddyfile(state)

    # Reload
    result = subprocess.run(
        [caddy_exe, "reload", "--config", str(caddyfile)],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
        return (False, f"Failed to reload Caddy: {error_msg}")

    return (True, "Caddy configuration reloaded")


def get_caddy_status(state: StateConfig) -> dict:
    """Get comprehensive Caddy status."""
    caddy_exe = find_caddy_executable()
    pid = get_caddy_pid()
    stored_pid = state.raw.get("proxy", {}).get("system", {}).get("caddy_pid")
    conflicts = check_port_conflicts([80, 443])

    status = {
        "installed": caddy_exe is not None,
        "executable": caddy_exe,
        "running": pid is not None,
        "pid": pid,
        "stored_pid": stored_pid,
        "pid_match": pid == stored_pid if (pid and stored_pid) else None,
        "port_conflicts": conflicts,
        "caddyfile": str(get_caddyfile_path(state)),
    }

    return status


def upgrade_to_system_mode(state: StateConfig) -> tuple[bool, str]:
    """
    Upgrade from Mode 1 (Gateway) to Mode 2 (System).

    Returns (success, message).
    """
    current_mode = state.proxy_mode

    if current_mode == "system":
        return (True, "Already in system mode")

    if current_mode == "external":
        return (False, "Cannot upgrade from external mode. Use 'devhost proxy transfer' instead.")

    # Check for Caddy
    caddy_exe = find_caddy_executable()
    if not caddy_exe:
        return (False, "Caddy not found. Install with: devhost install --caddy")

    # Check port conflicts
    conflicts = check_port_conflicts([80])
    if conflicts:
        print_port_conflicts(conflicts)
        return (False, "Resolve port conflicts before upgrading to system mode")

    # Start Caddy
    success, msg = start_caddy(state)
    if not success:
        return (False, f"Failed to start Caddy: {msg}")

    # Switch mode
    state.proxy_mode = "system"

    return (True, f"Upgraded to system mode. {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI Handlers
# ─────────────────────────────────────────────────────────────────────────────


def cmd_proxy_start():
    """Handle 'devhost proxy start' command."""
    state = StateConfig()
    mode = state.proxy_mode

    if mode == "off":
        print_warning("Proxy mode is 'off'. Set mode with 'devhost proxy upgrade --to gateway'.")
        return False

    if mode == "external":
        print_info("External proxy mode - Devhost does not manage the proxy process.")
        print_info("Manage your proxy manually or use your system's service manager.")
        return True

    if mode == "gateway":
        # Gateway mode uses the router, not Caddy
        print_info("Gateway mode uses the built-in router on port 7777.")
        print_info("Use 'devhost start' to start the router.")
        return True

    # System mode - start Caddy
    success, msg = start_caddy(state)
    if success:
        print_success(msg)
    else:
        print_error(msg)
    return success


def cmd_proxy_stop(force: bool = False):
    """Handle 'devhost proxy stop' command."""
    state = StateConfig()
    mode = state.proxy_mode

    if mode == "external":
        print_info("External proxy mode - Devhost does not manage the proxy process.")
        return True

    if mode == "gateway":
        print_info("Gateway mode uses the built-in router.")
        print_info("Use 'devhost stop' to stop the router.")
        return True

    # System mode - stop Caddy
    success, msg = stop_caddy(state, force)
    if success:
        print_success(msg)
    else:
        print_error(msg)
    return success


def cmd_proxy_status():
    """Handle 'devhost proxy status' command."""
    state = StateConfig()
    mode = state.proxy_mode

    console.print(f"\n[bold]Proxy Mode:[/bold] [cyan]{mode}[/cyan]")

    if mode == "gateway":
        port = state.gateway_port
        console.print(f"[bold]Gateway Port:[/bold] {port}")
        console.print("\n[dim]Use 'devhost status' for full status[/dim]")
        return True

    if mode == "system":
        status = get_caddy_status(state)

        console.print("\n[bold]Caddy Status:[/bold]")
        if status["installed"]:
            console.print(f"  Installed: [green]Yes[/green] ({status['executable']})")
        else:
            console.print("  Installed: [red]No[/red]")

        if status["running"]:
            console.print(f"  Running: [green]Yes[/green] (PID {status['pid']})")
        else:
            console.print("  Running: [yellow]No[/yellow]")

        if status["port_conflicts"]:
            console.print("\n[bold yellow]Port Conflicts:[/bold yellow]")
            for conflict in status["port_conflicts"]:
                console.print(f"  Port {conflict['port']}: {conflict['process']}")
        else:
            console.print("\n[bold]Ports 80/443:[/bold] [green]Available[/green]")

        return True

    if mode == "external":
        console.print("\n[dim]External proxy mode - Devhost does not manage the proxy[/dim]")
        driver = state.external_driver
        config_path = state.external_config_path
        console.print(f"\n[bold]Driver:[/bold] {driver}")
        if config_path:
            console.print(f"[bold]Config:[/bold] {config_path}")
        return True

    return True


def cmd_proxy_upgrade(to_mode: Literal["gateway", "system"]):
    """Handle 'devhost proxy upgrade' command."""
    state = StateConfig()

    if to_mode == "gateway":
        if state.proxy_mode == "gateway":
            print_info("Already in gateway mode")
            return True
        state.proxy_mode = "gateway"
        print_success("Switched to gateway mode")
        print_info(f"Access your apps at http://<name>.localhost:{state.gateway_port}")
        return True

    if to_mode == "system":
        # Check if running with admin on Windows
        if IS_WINDOWS:
            from .platform import is_admin

            if not is_admin():
                print_error("Administrator privileges required for system mode.")
                print_info("Run from an elevated PowerShell or use 'devhost install --system'.")
                return False

        success, msg = upgrade_to_system_mode(state)
        if success:
            print_success(msg)
            print_info("Access your apps at http://<name>.localhost (no port needed)")
        else:
            print_error(msg)
        return success

    return False


def cmd_proxy_reload():
    """Handle 'devhost proxy reload' command."""
    state = StateConfig()
    mode = state.proxy_mode

    if mode != "system":
        print_info(f"Reload is only available in system mode (current: {mode})")
        return True

    success, msg = reload_caddy(state)
    if success:
        print_success(msg)
    else:
        print_error(msg)
    return success
