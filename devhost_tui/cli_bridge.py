"""
CLI Bridge - Async-safe adapters for CLI functions.

Wraps synchronous devhost_cli functions so they can be called
safely from Textual workers (thread-based or async). Each bridge
class groups related CLI operations by domain.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

_pool = ThreadPoolExecutor(max_workers=4)


async def _run_sync(fn, *args, **kwargs):
    """Run a sync function in the thread pool, returning its result."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_pool, lambda: fn(*args, **kwargs))


# ---------------------------------------------------------------------------
# Router Bridge
# ---------------------------------------------------------------------------


class RouterBridge:
    """Manage the gateway router process."""

    @staticmethod
    async def is_running() -> tuple[bool, int | None]:
        from devhost_cli.router_manager import Router

        return await _run_sync(Router().is_running)

    @staticmethod
    async def start() -> bool:
        from devhost_cli.router_manager import Router

        return await _run_sync(Router().start)

    @staticmethod
    async def stop() -> bool:
        from devhost_cli.router_manager import Router

        return await _run_sync(Router().stop)

    @staticmethod
    async def health_check() -> bool:
        from devhost_cli.router_manager import Router

        router = Router()

        def _check():
            try:
                return router._check_health()
            except Exception:
                return False

        return await _run_sync(_check)


# ---------------------------------------------------------------------------
# Tunnel Bridge
# ---------------------------------------------------------------------------


@dataclass
class TunnelStatus:
    """Simplified tunnel information for the TUI."""

    route_name: str
    provider: str
    public_url: str | None
    pid: int | None
    started_at: float


class TunnelBridge:
    """Manage tunnel providers (cloudflared, ngrok, localtunnel)."""

    @staticmethod
    async def available_providers() -> list[str]:
        from devhost_cli.tunnel import detect_available_providers

        return await _run_sync(detect_available_providers)

    @staticmethod
    async def start(
        state,
        route_name: str,
        provider: str | None = None,
    ) -> tuple[bool, str]:
        from devhost_cli.tunnel import start_tunnel

        def _start():
            try:
                ok = start_tunnel(state, route_name, provider)
                msg = "Tunnel started" if ok else "Failed to start tunnel"
                return ok, msg
            except Exception as exc:
                return False, str(exc)

        return await _run_sync(_start)

    @staticmethod
    async def stop(state, route_name: str | None = None) -> tuple[bool, str]:
        from devhost_cli.tunnel import stop_tunnel

        def _stop():
            try:
                ok = stop_tunnel(state, route_name)
                msg = "Tunnel stopped" if ok else "No active tunnel found"
                return ok, msg
            except Exception as exc:
                return False, str(exc)

        return await _run_sync(_stop)

    @staticmethod
    async def status(state) -> list[TunnelStatus]:
        def _status():
            tunnels = state.get_all_tunnels()
            result = []
            for name, info in tunnels.items():
                result.append(
                    TunnelStatus(
                        route_name=name,
                        provider=info.get("provider", "unknown"),
                        public_url=info.get("public_url"),
                        pid=info.get("pid"),
                        started_at=info.get("started_at", 0),
                    )
                )
            return result

        return await _run_sync(_status)


# ---------------------------------------------------------------------------
# Proxy Bridge
# ---------------------------------------------------------------------------


class ProxyBridge:
    """Manage proxy modes, Caddy lifecycle, and external proxy integration."""

    # -- Caddy lifecycle --

    @staticmethod
    async def start_caddy(state) -> tuple[bool, str]:
        from devhost_cli.caddy_lifecycle import start_caddy

        return await _run_sync(start_caddy, state)

    @staticmethod
    async def stop_caddy(state, force: bool = False) -> tuple[bool, str]:
        from devhost_cli.caddy_lifecycle import stop_caddy

        return await _run_sync(stop_caddy, state, force)

    @staticmethod
    async def reload_caddy(state) -> tuple[bool, str]:
        from devhost_cli.caddy_lifecycle import reload_caddy

        return await _run_sync(reload_caddy, state)

    @staticmethod
    async def caddy_status(state) -> dict:
        from devhost_cli.caddy_lifecycle import get_caddy_status

        return await _run_sync(get_caddy_status, state)

    @staticmethod
    async def check_port_conflicts(ports: list[int] | None = None) -> list[dict]:
        from devhost_cli.caddy_lifecycle import check_port_conflicts

        return await _run_sync(check_port_conflicts, ports)

    # -- External proxy --

    @staticmethod
    async def discover_proxy_config(driver: str | None = None) -> list[tuple[str, Path]]:
        from devhost_cli.proxy import discover_proxy_config

        return await _run_sync(discover_proxy_config, driver)

    @staticmethod
    async def export_snippets(
        state,
        drivers: list[str],
        *,
        use_lock: bool = False,
        lock_path: Path | None = None,
    ) -> dict[str, Path]:
        from devhost_cli.proxy import export_snippets

        return await _run_sync(export_snippets, state, drivers, use_lock=use_lock, lock_path=lock_path)

    @staticmethod
    async def attach_to_config(
        state,
        config_path: Path,
        driver: str,
        *,
        validate: bool = True,
        use_lock: bool = False,
        lock_path: Path | None = None,
    ) -> tuple[bool, str]:
        from devhost_cli.proxy import attach_to_config

        return await _run_sync(
            attach_to_config,
            state,
            config_path,
            driver,
            validate=validate,
            use_lock=use_lock,
            lock_path=lock_path,
        )

    @staticmethod
    async def detach_from_config(
        state,
        config_path: Path,
        *,
        force: bool = False,
    ) -> tuple[bool, str]:
        from devhost_cli.proxy import detach_from_config

        return await _run_sync(detach_from_config, state, config_path, force=force)

    @staticmethod
    async def validate_proxy_config(driver: str, config_path: Path) -> tuple[bool, str]:
        from devhost_cli.proxy import validate_proxy_config

        return await _run_sync(validate_proxy_config, driver, config_path)

    @staticmethod
    async def check_proxy_drift(
        state,
        driver: str,
        config_path: Path | None = None,
        *,
        validate: bool = False,
    ) -> dict:
        from devhost_cli.proxy import check_proxy_drift

        return await _run_sync(check_proxy_drift, state, driver, config_path, validate=validate)

    @staticmethod
    async def accept_proxy_drift(
        state,
        driver: str,
        config_path: Path | None = None,
    ) -> tuple[bool, str]:
        from devhost_cli.proxy import accept_proxy_drift

        return await _run_sync(accept_proxy_drift, state, driver, config_path)

    @staticmethod
    async def write_lockfile(state, path: Path | None = None) -> Path:
        from devhost_cli.proxy import write_lockfile

        return await _run_sync(write_lockfile, state, path)

    @staticmethod
    async def apply_lockfile(
        state,
        path: Path | None = None,
        *,
        update_config: bool = True,
    ) -> tuple[bool, str]:
        from devhost_cli.proxy import apply_lockfile

        return await _run_sync(apply_lockfile, state, path, update_config=update_config)

    @staticmethod
    async def sync_proxy(
        state,
        driver: str,
        *,
        watch: bool = False,
        use_lock: bool = False,
        lock_path: Path | None = None,
    ) -> None:
        from devhost_cli.proxy import sync_proxy

        return await _run_sync(sync_proxy, state, driver, watch=watch, use_lock=use_lock, lock_path=lock_path)

    @staticmethod
    async def transfer_to_external(
        state,
        driver: str,
        *,
        config_path: str | None = None,
        auto_attach: bool = True,
        verify: bool = True,
        port: int = 80,
    ) -> tuple[bool, str]:
        from devhost_cli.proxy import transfer_to_external as _do_transfer

        path = Path(config_path) if config_path else None
        return await _run_sync(
            _do_transfer,
            state,
            driver,
            config_path=path,
            auto_attach=auto_attach,
            verify=verify,
            port=port,
        )

    @staticmethod
    async def generate_snippet(driver: str, routes: list) -> str:
        from devhost_cli.proxy import generate_snippet

        return await _run_sync(generate_snippet, driver, routes)


# ---------------------------------------------------------------------------
# Features Bridge
# ---------------------------------------------------------------------------


class FeaturesBridge:
    """Developer features: OAuth, QR, env sync, LAN."""

    @staticmethod
    async def get_lan_ip() -> str | None:
        from devhost_cli.features import get_lan_ip

        return await _run_sync(get_lan_ip)

    @staticmethod
    async def generate_qr_code(url: str, quiet: bool = True) -> str | None:
        from devhost_cli.features import generate_qr_code

        return await _run_sync(generate_qr_code, url, quiet)

    @staticmethod
    async def get_oauth_uris(
        name: str,
        domain: str = "localhost",
        port: int | None = None,
        scheme: str = "http",
    ) -> list[str]:
        from devhost_cli.features import get_oauth_uris

        return await _run_sync(get_oauth_uris, name, domain, port, scheme)

    @staticmethod
    async def sync_env_file(
        name: str | None = None,
        env_file: str = ".env",
        dry_run: bool = False,
    ) -> bool:
        from devhost_cli.features import sync_env_file

        return await _run_sync(sync_env_file, name, env_file, dry_run)


# ---------------------------------------------------------------------------
# Diagnostics Bridge
# ---------------------------------------------------------------------------


class DiagnosticsBridge:
    """Diagnostic bundle export and preview."""

    @staticmethod
    async def export_bundle(state, *, redact: bool = True) -> tuple[bool, Path | None, dict]:
        from devhost_cli.diagnostics import export_diagnostic_bundle

        return await _run_sync(export_diagnostic_bundle, state, redact=redact)

    @staticmethod
    async def preview_bundle(state, *, redact: bool = True) -> dict:
        from devhost_cli.diagnostics import preview_diagnostic_bundle

        return await _run_sync(preview_diagnostic_bundle, state, redact=redact)


# ---------------------------------------------------------------------------
# Scanner Bridge
# ---------------------------------------------------------------------------


class ScannerBridge:
    """Port scanning for ghost port detection."""

    @staticmethod
    async def scan_listening_ports(exclude_system: bool = True) -> list:
        from devhost_cli.scanner import scan_listening_ports

        return await _run_sync(scan_listening_ports, exclude_system)

    @staticmethod
    async def get_common_dev_ports() -> dict[int, str]:
        from devhost_cli.scanner import get_common_dev_ports

        return await _run_sync(get_common_dev_ports)

    @staticmethod
    async def detect_framework(name: str, port: int) -> str | None:
        from devhost_cli.scanner import detect_framework

        return await _run_sync(detect_framework, name, port)
