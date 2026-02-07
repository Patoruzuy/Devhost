"""
Background services for the TUI dashboard.

- StateWatcher: filesystem watcher for state.yml changes (via watchdog)
- ProbeService: periodic HTTP health probes for all routes
- LogTailService: tails router log files
- PortScanCache: TTL-cached port scan results
"""

from __future__ import annotations

import os
import re
import socket
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from textual import work
from textual.message import Message

from devhost_cli.scanner import ListeningPort, scan_listening_ports
from devhost_cli.state import StateConfig
from devhost_cli.validation import parse_target

if TYPE_CHECKING:
    from textual.app import App


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class StateFileChanged(Message):
    """Message posted when state.yml is modified externally."""


class ProbeComplete(Message):
    """Message posted when probe cycle completes."""

    def __init__(self, results: dict[str, dict]) -> None:
        self.results = results
        super().__init__()


class PortScanComplete(Message):
    """Message posted when port scan completes."""

    def __init__(self, ports: list[ListeningPort]) -> None:
        self.ports = ports
        super().__init__()


# ---------------------------------------------------------------------------
# StateWatcher  (uses watchdog for instant file-change notifications)
# ---------------------------------------------------------------------------


class StateWatcher:
    """Watch ``state.yml`` for external changes and notify the app.

    Falls back to mtime polling if watchdog is unavailable.
    """

    POLL_INTERVAL = 2.0  # seconds (fallback)

    def __init__(self, app: App):
        self._app = app
        self._state: StateConfig = getattr(app, "state", StateConfig())
        self._observer = None
        self._last_mtime: float | None = None

    def start(self) -> None:
        """Begin watching state.yml for changes."""
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            state_file = self._state.state_file

            class _Handler(FileSystemEventHandler):
                def __init__(self, watcher: StateWatcher):
                    self._watcher = watcher

                def on_modified(self, event):
                    if not event.is_directory and Path(event.src_path).name == state_file.name:
                        self._watcher._on_state_changed()

            self._observer = Observer()
            self._observer.schedule(_Handler(self), str(state_file.parent), recursive=False)
            self._observer.daemon = True
            self._observer.start()
        except ImportError:
            # Fallback: mtime polling via Textual timer
            self._last_mtime = self._get_mtime()
            self._app.set_interval(self.POLL_INTERVAL, self._poll_mtime, name="state_poll")

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer = None

    def _get_mtime(self) -> float | None:
        try:
            return self._state.state_file.stat().st_mtime
        except OSError:
            return None

    def _poll_mtime(self) -> None:
        mtime = self._get_mtime()
        if mtime is None:
            return
        if self._last_mtime is None:
            self._last_mtime = mtime
            return
        if mtime > self._last_mtime:
            self._last_mtime = mtime
            self._on_state_changed()

    def _on_state_changed(self) -> None:
        """Called when state.yml is modified on disk."""
        self._app.call_from_thread(self._app.post_message, StateFileChanged())


# ---------------------------------------------------------------------------
# ProbeService
# ---------------------------------------------------------------------------


class ProbeService:
    """Periodic HTTP/TCP health probes for registered routes."""

    INTERVAL = 30.0  # seconds between automatic probe cycles

    def __init__(self, app: App):
        self._app = app
        self._results: dict[str, dict] = {}
        self._last_probe_time: float | None = None

    @property
    def results(self) -> dict[str, dict]:
        return dict(self._results)

    @property
    def last_probe_time(self) -> float | None:
        return self._last_probe_time

    def start(self) -> None:
        self._app.set_interval(self.INTERVAL, self._schedule, name="probe_refresh")
        self._schedule()

    def _schedule(self) -> None:
        self._run_probes()

    @work(exclusive=True, thread=True)
    def _run_probes(self) -> None:
        """Probe all routes in a background thread."""
        session = getattr(self._app, "session", None)
        if not session:
            return

        routes = dict(session.routes)
        mode = session.proxy_mode
        domain = session.system_domain
        gateway_port = session.gateway_port

        listen_http = session.raw.get("proxy", {}).get("system", {}).get("listen_http", "127.0.0.1:80")
        listen_https = session.raw.get("proxy", {}).get("system", {}).get("listen_https", "127.0.0.1:443")
        if mode == "external":
            listen_http = session.raw.get("proxy", {}).get("external", {}).get("listen_http") or listen_http
            listen_https = session.raw.get("proxy", {}).get("external", {}).get("listen_https") or listen_https
        probe_targets = self._compute_probe_targets(mode, gateway_port, listen_http, listen_https)
        results: dict[str, dict] = {}

        for name, route in routes.items():
            enabled = route.get("enabled", True)
            route_domain = route.get("domain", domain)
            host_header = f"{name}.{route_domain}"

            upstream = str(route.get("upstream", ""))
            parsed = parse_target(upstream)
            if not parsed:
                results[name] = {
                    "upstream_ok": False,
                    "route_ok": False,
                    "latency_ms": None,
                    "message": "invalid upstream",
                    "checked_at": time.strftime("%H:%M:%S"),
                }
                continue

            _scheme, upstream_host, upstream_port = parsed
            upstream_ok = False
            upstream_error = None
            if enabled:
                try:
                    with socket.create_connection((upstream_host, upstream_port), timeout=0.5):
                        upstream_ok = True
                except OSError:
                    upstream_error = f"TCP connect failed to {upstream_host}:{upstream_port}"

            route_ok = None
            latency_ms = None
            route_error = None
            used_scheme = None
            used_port = None
            if enabled and mode != "off":
                for scheme, port in probe_targets:
                    url = f"{scheme}://127.0.0.1:{port}/"
                    start = time.perf_counter()
                    try:
                        resp = httpx.get(
                            url,
                            headers={"Host": host_header},
                            timeout=1.0,
                            follow_redirects=False,
                            verify=scheme != "https",
                        )
                        latency_ms = (time.perf_counter() - start) * 1000
                        route_ok = resp.status_code < 500
                        route_error = f"HTTP {resp.status_code}" if not route_ok else None
                        used_scheme = scheme
                        used_port = port
                        if route_ok:
                            break
                    except Exception as exc:
                        latency_ms = (time.perf_counter() - start) * 1000
                        route_ok = False
                        route_error = str(exc)
                        used_scheme = scheme
                        used_port = port
                        continue

            results[name] = {
                "upstream_ok": upstream_ok,
                "upstream_error": upstream_error,
                "route_ok": route_ok,
                "route_error": route_error,
                "latency_ms": latency_ms,
                "route_scheme": used_scheme,
                "route_port": used_port,
                "message": None,
                "checked_at": time.strftime("%H:%M:%S"),
            }

        self._results = results
        self._last_probe_time = time.time()
        self._app.call_from_thread(self._app.post_message, ProbeComplete(results))

    @staticmethod
    def _parse_listen_port(value: str, default_port: int) -> int:
        if not value:
            return default_port
        if ":" in value:
            _, port_str = value.rsplit(":", 1)
            try:
                return int(port_str)
            except ValueError:
                return default_port
        try:
            return int(value)
        except ValueError:
            return default_port

    @staticmethod
    def _compute_probe_targets(
        mode: str, gateway_port: int, listen_http: str, listen_https: str
    ) -> list[tuple[str, int]]:
        http_port = ProbeService._parse_listen_port(listen_http, 80)
        https_port = ProbeService._parse_listen_port(listen_https, 443)
        targets: list[tuple[str, int]] = []
        if mode == "gateway":
            targets.append(("http", gateway_port))
        elif mode != "off":
            targets.append(("https", https_port))
            if http_port != https_port:
                targets.append(("http", http_port))
        return targets


# ---------------------------------------------------------------------------
# LogTailService
# ---------------------------------------------------------------------------


class LogTailService:
    """Tail router log files with filtering."""

    INTERVAL = 1.0
    BUFFER_SIZE = 200
    COPY_LINES = 200

    LEVEL_MARKERS = {
        "info": ["[info]", " info ", "INFO", "info"],
        "warn": ["[warn]", "WARNING", "warn", "warning"],
        "error": ["[error]", "ERROR", "error", "exception", "traceback"],
    }

    def __init__(self, app: App):
        self._app = app
        self._state: StateConfig = getattr(app, "state", StateConfig())
        self._buffers: dict[str, deque[str]] = {}
        self._offsets: dict[str, int] = {}
        self._filter: str = ""
        self._levels: set[str] = {"info", "warn", "error"}

    @property
    def text_filter(self) -> str:
        return self._filter

    @text_filter.setter
    def text_filter(self, value: str) -> None:
        self._filter = value.strip()

    @property
    def level_filter(self) -> set[str]:
        return set(self._levels)

    @level_filter.setter
    def level_filter(self, levels: set[str]) -> None:
        self._levels = set(levels)

    def get_buffer(self, route_name: str) -> list[str]:
        buf = self._buffers.get(route_name)
        return list(buf) if buf else []

    def get_filtered_lines(self, route_name: str) -> list[str]:
        lines = self.get_buffer(route_name)
        lines = self._apply_levels(lines)
        return self._apply_filter(lines)

    def get_copyable_text(self, route_name: str) -> str:
        lines = self.get_filtered_lines(route_name)
        tail = lines[-self.COPY_LINES :]
        return "\n".join(tail)

    def start(self) -> None:
        self._app.set_interval(self.INTERVAL, self._schedule, name="log_tail")

    def _schedule(self) -> None:
        selected = getattr(self._app, "selected_route", None)
        if selected:
            self._tail(selected)

    @work(exclusive=True, thread=True)
    def _tail(self, route_name: str) -> None:
        log_path = self._resolve_log_path(route_name)
        if not log_path:
            return

        path_key = str(log_path)
        offset = self._offsets.get(path_key, 0)
        try:
            with open(log_path, encoding="utf-8", errors="ignore") as handle:
                handle.seek(offset)
                new_data = handle.read()
                self._offsets[path_key] = handle.tell()
        except OSError:
            return

        if not new_data:
            return

        lines = new_data.splitlines()
        buffer = self._buffers.setdefault(route_name, deque(maxlen=self.BUFFER_SIZE))
        buffer.extend(lines)

    def _resolve_log_path(self, route_name: str) -> Path | None:
        session = getattr(self._app, "session", None)
        if session:
            route = session.get_route(route_name)
            if route:
                configured = route.get("log_path")
                if configured:
                    return Path(str(configured))

        candidates = [
            self._state.devhost_dir / "logs" / f"{route_name}.log",
            self._state.devhost_dir / "logs" / "devhost-router.log",
            Path("/tmp/devhost-router.log"),
        ]
        temp = os.environ.get("TEMP")
        if temp:
            candidates.append(Path(temp) / "devhost-router.log")
        for path in candidates:
            if path.exists():
                return path
        return None

    def _apply_filter(self, lines: list[str]) -> list[str]:
        if not self._filter:
            return lines
        term = self._filter.lower()
        return [line for line in lines if term in line.lower()]

    def _apply_levels(self, lines: list[str]) -> list[str]:
        if not self._levels:
            return lines
        filtered = []
        for line in lines:
            lower = line.lower()
            matched = False
            for level in self._levels:
                for marker in self.LEVEL_MARKERS.get(level, []):
                    if marker.lower() in lower:
                        matched = True
                        break
                if matched:
                    break
            if matched or not self._levels:
                filtered.append(line)
        return filtered

    @staticmethod
    def format_lines(lines: list[str], highlight: str = "") -> list[str]:
        """Format log lines with optional highlight for filter term."""
        from rich.markup import escape

        if not highlight:
            return [escape(line) for line in lines]
        pattern = re.compile(re.escape(highlight), re.IGNORECASE)
        formatted: list[str] = []
        for line in lines:
            if not pattern.search(line):
                formatted.append(escape(line))
                continue
            parts: list[str] = []
            last = 0
            for match in pattern.finditer(line):
                parts.append(escape(line[last : match.start()]))
                parts.append(f"[reverse]{escape(match.group(0))}[/reverse]")
                last = match.end()
            parts.append(escape(line[last:]))
            formatted.append("".join(parts))
        return formatted


# ---------------------------------------------------------------------------
# PortScanCache
# ---------------------------------------------------------------------------


class PortScanCache:
    """TTL-cached port scan results for ghost port detection."""

    TTL = 30.0  # seconds

    def __init__(self, app: App):
        self._app = app
        self._cache: list[ListeningPort] = []
        self._ts: float | None = None
        self._inflight = False

    @property
    def ports(self) -> list[ListeningPort]:
        return list(self._cache)

    @property
    def in_progress(self) -> bool:
        return self._inflight or self.is_stale

    @property
    def is_stale(self) -> bool:
        if self._ts is None:
            return True
        return (time.monotonic() - self._ts) > self.TTL

    def ensure_fresh(self) -> None:
        """Trigger a scan if the cache is stale."""
        if self._inflight or not self.is_stale:
            return
        self._inflight = True
        self._scan()

    # Aliases used by app.py
    ensure_scan = ensure_fresh

    def get_results(self) -> tuple[list[ListeningPort], bool]:
        return list(self._cache), self.in_progress

    @work(exclusive=True, thread=True)
    def _scan(self) -> None:
        ports = scan_listening_ports()
        self._cache = ports
        self._ts = time.monotonic()
        self._inflight = False
        self._app.call_from_thread(self._app.post_message, PortScanComplete(ports))
