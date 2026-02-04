"""
Devhost Tunnel Module

Provides integration with tunnel providers for exposing local services to the internet:
- cloudflared (Cloudflare Tunnel)
- ngrok
- localtunnel

Usage:
    devhost tunnel start [name]    # Start tunnel for a route
    devhost tunnel stop [name]     # Stop tunnel
    devhost tunnel status          # Show active tunnels
"""

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .output import msg_error, msg_info, msg_success, msg_warning
from .state import StateConfig

TunnelProvider = Literal["cloudflared", "ngrok", "localtunnel"]


@dataclass
class TunnelInfo:
    """Information about an active tunnel."""

    provider: TunnelProvider
    route_name: str
    local_port: int
    public_url: str | None
    pid: int | None
    started_at: float


def find_tunnel_executable(provider: TunnelProvider) -> str | None:
    """Find the executable for a tunnel provider."""
    if provider == "cloudflared":
        # Check common locations
        candidates = ["cloudflared"]
        if os.name == "nt":
            candidates.extend(
                [
                    r"C:\Program Files\cloudflared\cloudflared.exe",
                    r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
                ]
            )
        else:
            candidates.extend(
                [
                    "/usr/local/bin/cloudflared",
                    "/usr/bin/cloudflared",
                    str(Path.home() / ".local" / "bin" / "cloudflared"),
                ]
            )

    elif provider == "ngrok":
        candidates = ["ngrok"]
        if os.name == "nt":
            candidates.extend(
                [
                    r"C:\Program Files\ngrok\ngrok.exe",
                    str(Path.home() / "ngrok" / "ngrok.exe"),
                ]
            )
        else:
            candidates.extend(
                [
                    "/usr/local/bin/ngrok",
                    "/usr/bin/ngrok",
                    str(Path.home() / "ngrok"),
                ]
            )

    elif provider == "localtunnel":
        # localtunnel is typically installed via npm
        candidates = ["lt"]
        if os.name == "nt":
            candidates.append("lt.cmd")
        else:
            candidates.extend(
                [
                    "/usr/local/bin/lt",
                    str(Path.home() / ".npm-global" / "bin" / "lt"),
                ]
            )
    else:
        return None

    # Try shutil.which first for PATH lookup
    for cmd in candidates:
        if os.path.isabs(cmd):
            if Path(cmd).exists():
                return cmd
        else:
            found = shutil.which(cmd)
            if found:
                return found

    return None


def detect_available_providers() -> list[TunnelProvider]:
    """Detect which tunnel providers are available."""
    available = []
    for provider in ["cloudflared", "ngrok", "localtunnel"]:
        if find_tunnel_executable(provider):
            available.append(provider)
    return available


def start_tunnel(
    state: StateConfig,
    route_name: str | None = None,
    provider: TunnelProvider | None = None,
) -> bool:
    """Start a tunnel for a route.

    Args:
        state: The StateConfig instance
        route_name: Name of the route to tunnel (uses first if None)
        provider: Tunnel provider to use (auto-detect if None)

    Returns:
        True if tunnel started successfully
    """
    # Resolve route
    if not route_name:
        routes = state.routes
        if not routes:
            msg_error("No routes configured. Add a route first.")
            return False
        route_name = next(iter(routes.keys()))

    route = state.get_route(route_name)
    if not route:
        msg_error(f"Route '{route_name}' not found.")
        return False

    # Parse upstream to get port
    upstream = route.get("upstream", "")
    if ":" in upstream:
        port = int(upstream.split(":")[-1])
    elif upstream.isdigit():
        port = int(upstream)
    else:
        msg_error(f"Cannot determine port from upstream: {upstream}")
        return False

    # Detect or validate provider
    if not provider:
        available = detect_available_providers()
        if not available:
            msg_error("No tunnel providers found.")
            msg_info("Install one of: cloudflared, ngrok, localtunnel")
            msg_info(
                "  cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
            )
            msg_info("  ngrok: https://ngrok.com/download")
            msg_info("  localtunnel: npm install -g localtunnel")
            return False
        provider = available[0]
        msg_info(f"Using provider: {provider}")
    else:
        exe = find_tunnel_executable(provider)
        if not exe:
            msg_error(f"Provider '{provider}' not found.")
            return False

    # Check if tunnel already running for this route
    active = state.get_active_tunnel(route_name)
    if active:
        msg_warning(f"Tunnel already running for '{route_name}'")
        if active.get("public_url"):
            msg_info(f"URL: {active['public_url']}")
        return True

    exe = find_tunnel_executable(provider)
    if not exe:
        msg_error(f"Cannot find {provider} executable")
        return False

    # Start the tunnel process
    msg_info(f"Starting {provider} tunnel for {route_name} (port {port})...")

    try:
        if provider == "cloudflared":
            proc = _start_cloudflared(exe, port, route_name)
        elif provider == "ngrok":
            proc = _start_ngrok(exe, port, route_name)
        elif provider == "localtunnel":
            proc = _start_localtunnel(exe, port, route_name)
        else:
            msg_error(f"Unknown provider: {provider}")
            return False

        if not proc:
            return False

        # Record the tunnel in state
        tunnel_info = {
            "provider": provider,
            "route_name": route_name,
            "local_port": port,
            "pid": proc.pid,
            "started_at": time.time(),
            "public_url": None,  # Will be updated when URL is detected
        }

        state.set_tunnel(route_name, tunnel_info)

        # Try to get the public URL (provider-specific)
        public_url = _get_tunnel_url(provider, proc, route_name)
        if public_url:
            tunnel_info["public_url"] = public_url
            state.set_tunnel(route_name, tunnel_info)
            msg_success(f"Tunnel started: {public_url}")
        else:
            msg_success(f"Tunnel started (PID: {proc.pid})")
            msg_info("Public URL will be available shortly...")

        return True

    except Exception as e:
        msg_error(f"Failed to start tunnel: {e}")
        return False


def _start_cloudflared(exe: str, port: int, route_name: str) -> subprocess.Popen | None:
    """Start a cloudflared tunnel."""
    cmd = [exe, "tunnel", "--url", f"http://127.0.0.1:{port}"]

    # Create log file for output
    log_dir = Path.home() / ".devhost" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"cloudflared-{route_name}.log"

    try:
        with open(log_file, "w") as f:
            proc = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        return proc
    except Exception as e:
        msg_error(f"Failed to start cloudflared: {e}")
        return None


def _start_ngrok(exe: str, port: int, route_name: str) -> subprocess.Popen | None:
    """Start an ngrok tunnel."""
    cmd = [exe, "http", str(port), "--log=stdout", "--log-format=json"]

    # Create log file for output
    log_dir = Path.home() / ".devhost" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"ngrok-{route_name}.log"

    try:
        with open(log_file, "w") as f:
            proc = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        return proc
    except Exception as e:
        msg_error(f"Failed to start ngrok: {e}")
        return None


def _start_localtunnel(exe: str, port: int, route_name: str) -> subprocess.Popen | None:
    """Start a localtunnel."""
    cmd = [exe, "--port", str(port)]

    # Create log file for output
    log_dir = Path.home() / ".devhost" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"localtunnel-{route_name}.log"

    try:
        with open(log_file, "w") as f:
            proc = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        return proc
    except Exception as e:
        msg_error(f"Failed to start localtunnel: {e}")
        return None


def _get_tunnel_url(provider: TunnelProvider, proc: subprocess.Popen, route_name: str) -> str | None:
    """Try to get the public URL from a tunnel provider."""
    log_dir = Path.home() / ".devhost" / "logs"

    # Wait a bit for the tunnel to start
    time.sleep(2)

    if provider == "cloudflared":
        log_file = log_dir / f"cloudflared-{route_name}.log"
        try:
            content = log_file.read_text()
            # Look for URL in cloudflared output
            for line in content.split("\n"):
                if "https://" in line and ".trycloudflare.com" in line:
                    # Extract URL
                    import re

                    match = re.search(r"(https://[a-z0-9-]+\.trycloudflare\.com)", line)
                    if match:
                        return match.group(1)
        except Exception:
            pass

    elif provider == "ngrok":
        # ngrok has an API at localhost:4040
        try:
            import requests

            resp = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=5)
            data = resp.json()
            tunnels = data.get("tunnels", [])
            if tunnels:
                return tunnels[0].get("public_url")
        except Exception:
            pass

    elif provider == "localtunnel":
        log_file = log_dir / f"localtunnel-{route_name}.log"
        try:
            content = log_file.read_text()
            # localtunnel prints: "your url is: https://xxx.loca.lt"
            for line in content.split("\n"):
                if "your url is:" in line.lower():
                    parts = line.split(":")
                    if len(parts) >= 3:
                        return ":".join(parts[-2:]).strip()
        except Exception:
            pass

    return None


def stop_tunnel(state: StateConfig, route_name: str | None = None) -> bool:
    """Stop a tunnel.

    Args:
        state: The StateConfig instance
        route_name: Name of the route (stops all if None)

    Returns:
        True if stopped successfully
    """
    tunnels = state.get_all_tunnels()

    if not tunnels:
        msg_info("No active tunnels.")
        return True

    if route_name:
        if route_name not in tunnels:
            msg_error(f"No tunnel for route '{route_name}'")
            return False
        tunnels_to_stop = {route_name: tunnels[route_name]}
    else:
        tunnels_to_stop = tunnels

    success = True
    for name, tunnel in tunnels_to_stop.items():
        pid = tunnel.get("pid")
        if pid:
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
                else:
                    os.kill(pid, 15)  # SIGTERM
                msg_success(f"Stopped tunnel for '{name}' (PID: {pid})")
            except Exception as e:
                msg_warning(f"Failed to stop tunnel for '{name}': {e}")
                success = False

        state.remove_tunnel(name)

    return success


def tunnel_status(state: StateConfig) -> bool:
    """Show status of active tunnels."""
    tunnels = state.get_all_tunnels()

    if not tunnels:
        msg_info("No active tunnels.")
        msg_info("Start one with: devhost tunnel start [route_name]")
        return True

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Active Tunnels")
    table.add_column("Route", style="cyan")
    table.add_column("Provider", style="magenta")
    table.add_column("Port", style="yellow")
    table.add_column("Public URL", style="green")
    table.add_column("PID", style="dim")

    for name, tunnel in tunnels.items():
        # Check if process still running
        pid = tunnel.get("pid")
        running = False
        if pid:
            try:
                if os.name == "nt":
                    result = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {pid}"],
                        capture_output=True,
                        text=True,
                    )
                    running = str(pid) in result.stdout
                else:
                    os.kill(pid, 0)  # Check if process exists
                    running = True
            except Exception:
                pass

        if not running:
            # Clean up dead tunnel
            state.remove_tunnel(name)
            continue

        # Try to refresh public URL if not set
        public_url = tunnel.get("public_url") or "..."

        table.add_row(
            name,
            tunnel.get("provider", "?"),
            str(tunnel.get("local_port", "?")),
            public_url,
            str(pid) if pid else "-",
        )

    console.print(table)
    return True


# CLI command handlers
def cmd_tunnel_start(route_name: str | None = None, provider: str | None = None) -> bool:
    """CLI handler for 'devhost tunnel start'."""
    state = StateConfig()
    return start_tunnel(
        state,
        route_name,
        provider if provider in ("cloudflared", "ngrok", "localtunnel") else None,
    )


def cmd_tunnel_stop(route_name: str | None = None) -> bool:
    """CLI handler for 'devhost tunnel stop'."""
    state = StateConfig()
    return stop_tunnel(state, route_name)


def cmd_tunnel_status() -> bool:
    """CLI handler for 'devhost tunnel status'."""
    state = StateConfig()
    return tunnel_status(state)
