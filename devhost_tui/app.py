"""
Devhost TUI - Main Application

Interactive terminal dashboard for managing local development routing.
"""

import os
import socket
import time
from collections import deque
from pathlib import Path

import httpx
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Static,
)

from devhost_cli.state import StateConfig
from .session import SessionState
from devhost_cli.validation import parse_target

from .scanner import ListeningPort, scan_listening_ports
from .widgets import DetailsPane, Sidebar, StatusGrid


class DevhostDashboard(App):
    """The main Devhost TUI application."""

    TITLE = "Devhost Dashboard"
    SUB_TITLE = "Local Development Router"
    STATE_WATCH_INTERVAL = 2.0
    PROBE_INTERVAL = 30.0
    INTEGRITY_INTERVAL = 60.0
    LOG_TAIL_INTERVAL = 1.0
    LOG_BUFFER_LINES = 200
    PORT_SCAN_TTL = 30.0

    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 2;
        grid-columns: 1fr 3fr 1fr;
        grid-rows: 1fr 1fr;
    }

    #next-action {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
        border-top: solid $primary-darken-2;
        color: $text;
    }

    #sidebar {
        column-span: 1;
        row-span: 2;
        background: $surface;
        border-right: solid $primary;
        padding: 1;
    }

    #ownership-banner {
        margin: 0 1 1 1;
        padding: 0 1;
        background: $surface-darken-1;
        border: round $primary-darken-2;
    }

    #main-grid {
        column-span: 2;
        row-span: 1;
        padding: 1;
    }

    #details {
        column-span: 2;
        row-span: 1;
        background: $surface;
        border-top: solid $primary;
        padding: 1;
    }

    .section-title {
        text-style: bold;
        color: $text;
        padding: 0 1;
        margin-bottom: 1;
    }

    StatusGrid {
        height: 100%;
    }

    StatusGrid > DataTable {
        height: 100%;
    }

    .status-ok {
        color: $success;
    }

    .status-warning {
        color: $warning;
    }

    .status-error {
        color: $error;
    }

    .mode-badge {
        padding: 0 1;
        background: $primary-darken-2;
    }

    .mode-gateway {
        background: $success-darken-2;
    }

    .mode-system {
        background: $primary-darken-2;
    }

    .mode-external {
        background: $warning-darken-2;
    }
    """

    BINDINGS = [
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("ctrl+i", "integrity_check", "Integrity"),
        Binding("ctrl+p", "probe_routes", "Probe"),
        Binding("ctrl+s", "apply_changes", "Apply"),
        Binding("e", "external_proxy", "External Proxy"),
        Binding("ctrl+x", "emergency_reset", "Emergency Reset"),
        Binding("a", "add_route", "Add Route"),
        Binding("d", "delete_route", "Delete Route"),
        Binding("o", "open_url", "Open URL"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.state = StateConfig()
        self.session = SessionState(self.state)
        self.selected_route: str | None = None
        self._last_state_mtime: float | None = None
        self._background_probe_enabled = True
        self._background_integrity_enabled = True
        self._log_tail_enabled = True
        self._probe_results: dict[str, dict] = {}
        self._integrity_results: dict[str, tuple[bool, str]] | None = None
        self._log_buffers: dict[str, deque[str]] = {}
        self._log_offsets: dict[str, int] = {}
        self._port_scan_cache: list[ListeningPort] = []
        self._port_scan_ts: float | None = None
        self._port_scan_inflight = False

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Sidebar(id="sidebar")
        yield StatusGrid(id="main-grid")
        yield DetailsPane(id="details")
        yield Static("", id="next-action")
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        self.refresh_data()
        self._start_background_tasks()

    def _start_background_tasks(self) -> None:
        """Start background workers and watchers."""
        self._last_state_mtime = self._get_state_mtime()
        self.set_interval(self.STATE_WATCH_INTERVAL, self._poll_state_file, name="state_watch")
        self.set_interval(self.PROBE_INTERVAL, self._schedule_probe_refresh, name="probe_refresh")
        self.set_interval(self.INTEGRITY_INTERVAL, self._schedule_integrity_refresh, name="integrity_refresh")
        self.set_interval(self.LOG_TAIL_INTERVAL, self._schedule_log_tail, name="log_tail")
        if self._background_probe_enabled:
            self._probe_routes_worker()
        if self._background_integrity_enabled:
            self._integrity_worker()
        self._ensure_port_scan()

    def _get_state_mtime(self) -> float | None:
        try:
            return self.state.state_file.stat().st_mtime
        except OSError:
            return None

    def _poll_state_file(self) -> None:
        mtime = self._get_state_mtime()
        if mtime is None:
            return
        if self._last_state_mtime is None:
            self._last_state_mtime = mtime
            return
        if mtime > self._last_state_mtime:
            self._last_state_mtime = mtime
            if self.session.has_changes():
                self.notify("State updated on disk. Apply or discard your draft to sync.", severity="warning")
            else:
                self.session.reset()
                self.refresh_data()

    def _schedule_probe_refresh(self) -> None:
        if not self._background_probe_enabled:
            return
        self._probe_routes_worker()

    def _schedule_integrity_refresh(self) -> None:
        if not self._background_integrity_enabled:
            return
        self._integrity_worker()

    def _schedule_log_tail(self) -> None:
        if not self._log_tail_enabled or not self.selected_route:
            return
        self._log_tail_worker(self.selected_route)

    def _port_scan_is_stale(self) -> bool:
        if self._port_scan_ts is None:
            return True
        return (time.monotonic() - self._port_scan_ts) > self.PORT_SCAN_TTL

    def get_port_scan_results(self) -> tuple[list[ListeningPort], bool]:
        in_progress = self._port_scan_inflight or self._port_scan_is_stale()
        return list(self._port_scan_cache), in_progress

    def _ensure_port_scan(self) -> None:
        if self._port_scan_inflight or not self._port_scan_is_stale():
            return
        self._port_scan_inflight = True
        self._port_scan_worker()

    def _apply_port_scan_results(self, ports: list[ListeningPort]) -> None:
        self._port_scan_cache = ports
        self._port_scan_ts = time.monotonic()
        self._port_scan_inflight = False

        from .modals import AddRouteWizard

        for screen in reversed(self.screen_stack):
            if isinstance(screen, AddRouteWizard):
                screen.set_detected_ports(ports)
                break

    @work(exclusive=True, thread=True)
    def _port_scan_worker(self) -> list[ListeningPort]:
        ports = scan_listening_ports()
        self.call_from_thread(self._apply_port_scan_results, ports)
        return ports

    def _parse_listen_port(self, value: str, default_port: int) -> int:
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
        http_port = DevhostDashboard._parse_listen_port_static(listen_http, 80)
        https_port = DevhostDashboard._parse_listen_port_static(listen_https, 443)
        targets: list[tuple[str, int]] = []
        if mode == "gateway":
            targets.append(("http", gateway_port))
        elif mode != "off":
            targets.append(("https", https_port))
            if http_port != https_port:
                targets.append(("http", http_port))
        return targets

    @staticmethod
    def _parse_listen_port_static(value: str, default_port: int) -> int:
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

    def _resolve_log_path(self, route_name: str) -> Path | None:
        route = self.session.get_route(route_name)
        if route:
            configured = route.get("log_path")
            if configured:
                return Path(str(configured))

        candidates = [
            self.state.devhost_dir / "logs" / f"{route_name}.log",
            self.state.devhost_dir / "logs" / "devhost-router.log",
            Path("/tmp/devhost-router.log"),
        ]
        temp = os.environ.get("TEMP")
        if temp:
            candidates.append(Path(temp) / "devhost-router.log")
        for path in candidates:
            if path.exists():
                return path
        return None

    def _apply_probe_results(self, results: dict[str, dict]) -> None:
        self._probe_results = results
        self.refresh_data()

    def _apply_integrity_results(self, results: dict[str, tuple[bool, str]]) -> None:
        self._integrity_results = results
        self.refresh_data()

    def _append_logs(self, route_name: str, lines: list[str]) -> None:
        buffer = self._log_buffers.setdefault(route_name, deque(maxlen=self.LOG_BUFFER_LINES))
        buffer.extend(lines)
        if self.selected_route == route_name:
            self._refresh_logs_view()

    def _set_logs_message(self, message: str) -> None:
        details = self.query_one(DetailsPane)
        logs = details.query_one("#logs-content")
        logs.update(message)

    def _refresh_logs_view(self) -> None:
        if not self.selected_route:
            return
        log_path = self._resolve_log_path(self.selected_route)
        buffer = self._log_buffers.get(self.selected_route)
        if not buffer:
            if log_path and log_path.exists():
                self._set_logs_message(f"Tailing {log_path} (no new lines yet).")
            else:
                self._set_logs_message("No logs available for this route.")
            return
        content = "\n".join(buffer)
        self._set_logs_message(content)

    @work(exclusive=True, thread=True)
    def _probe_routes_worker(self) -> dict:
        routes = dict(self.session.routes)
        mode = self.session.proxy_mode
        domain = self.session.system_domain
        gateway_port = self.session.gateway_port

        listen_http = self.session.raw.get("proxy", {}).get("system", {}).get("listen_http", "127.0.0.1:80")
        listen_https = self.session.raw.get("proxy", {}).get("system", {}).get("listen_https", "127.0.0.1:443")
        if mode == "external":
            listen_http = self.session.raw.get("proxy", {}).get("external", {}).get("listen_http") or listen_http
            listen_https = self.session.raw.get("proxy", {}).get("external", {}).get("listen_https") or listen_https
        probe_targets = self._compute_probe_targets(mode, gateway_port, listen_http, listen_https)
        probe_results: dict[str, dict] = {}

        for name, route in routes.items():
            enabled = route.get("enabled", True)
            route_domain = route.get("domain", domain)
            host_header = f"{name}.{route_domain}"

            upstream = str(route.get("upstream", ""))
            parsed = parse_target(upstream)
            if not parsed:
                probe_results[name] = {
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
                    upstream_ok = False
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
                            verify=False if scheme == "https" else True,
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

            probe_results[name] = {
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

        self.call_from_thread(self._apply_probe_results, probe_results)
        return probe_results

    @work(exclusive=True, thread=True)
    def _integrity_worker(self) -> dict:
        results = self.state.check_all_integrity()
        self.call_from_thread(self._apply_integrity_results, results)
        return results

    @work(exclusive=True, thread=True)
    def _log_tail_worker(self, route_name: str) -> None:
        log_path = self._resolve_log_path(route_name)
        if not log_path:
            self.call_from_thread(self._set_logs_message, "No log file found for this route.")
            return

        path_key = str(log_path)
        offset = self._log_offsets.get(path_key, 0)
        try:
            with open(log_path, encoding="utf-8", errors="ignore") as handle:
                handle.seek(offset)
                new_data = handle.read()
                self._log_offsets[path_key] = handle.tell()
        except OSError:
            self.call_from_thread(self._set_logs_message, "Unable to read log file.")
            return

        if not new_data:
            return

        lines = new_data.splitlines()
        self.call_from_thread(self._append_logs, route_name, lines)

    def refresh_data(self) -> None:
        """Refresh all data from state."""
        self.state.reload()
        if not self.session.has_changes():
            self.session.reset()
        if self._integrity_results is None:
            self._integrity_results = self.state.check_all_integrity()
        integrity_results = self._integrity_results
        integrity_ok = None
        if integrity_results is not None:
            integrity_ok = all(ok for ok, _ in integrity_results.values())

        # Update status grid
        grid = self.query_one(StatusGrid)
        grid.update_routes(
            self.session.routes,
            self.session.proxy_mode,
            self.session.system_domain,
            self.session.gateway_port,
            self._probe_results,
            integrity_ok,
        )

        # Update sidebar
        sidebar = self.query_one(Sidebar)
        sidebar.update_state(self.session, integrity_results)

        # Update details if a route is selected
        if self.selected_route:
            details = self.query_one(DetailsPane)
            route = self.session.get_route(self.selected_route)
            if route:
                details.show_route(
                    self.selected_route,
                    route,
                    self.session,
                    self._probe_results,
                    integrity_results,
                    self.state,
                )

        next_action = self._compute_next_action()
        next_bar = self.query_one("#next-action", Static)
        next_bar.update(next_action)

    def _compute_next_action(self) -> str:
        if self.session.has_changes():
            return "Next: Apply draft changes (Ctrl+S)"
        if not self.session.routes:
            return "Next: Add your first route (A)"
        if self._integrity_results:
            drift = [path for path, (ok, _) in self._integrity_results.items() if not ok]
            if drift:
                return f"Next: Resolve integrity drift ({len(drift)} file(s)) in Integrity tab"
        if self.session.proxy_mode == "external" and not self.state.external_config_path:
            return "Next: Attach external proxy config (E)"
        return "Next: Probe routes (Ctrl+P) or run integrity check (Ctrl+I)"

    def action_refresh(self) -> None:
        """Refresh data."""
        self.refresh_data()
        self.notify("Data refreshed", severity="information")

    def action_integrity_check(self) -> None:
        """Run integrity check."""
        results = self.state.check_all_integrity()
        self._apply_integrity_results(results)
        issues = [path for path, (ok, _) in results.items() if not ok]
        if issues:
            self.notify(f"Integrity issues found: {len(issues)} files", severity="warning")
        else:
            self.notify("All files OK", severity="information")

    def resolve_integrity(self, filepath: str, action: str) -> None:
        """Resolve integrity drift for a tracked file."""
        path = Path(filepath)
        if action == "accept":
            if not path.exists():
                self.notify("File is missing. Cannot accept.", severity="error")
                return
            self.state.record_hash(path)
            message = "Integrity updated to match current file."
        elif action == "ignore":
            self.state.remove_hash(path)
            message = "Stopped tracking file integrity."
        else:
            return

        results = self.state.check_all_integrity()
        self._apply_integrity_results(results)
        self.notify(message, severity="information")

    def action_probe_routes(self) -> None:
        """Probe all routes."""
        self.notify("Probing routes...", severity="information")
        self._background_probe_enabled = True
        self._probe_routes_worker()

    def queue_route_change(self, name: str, upstream: str, mode: str) -> None:
        """Stage a route change in the session state."""
        self.session.set_route(name, upstream, domain=self.session.system_domain, enabled=True)
        self.session.set_proxy_mode(mode)
        if mode == "external":
            self.session.set_external_config(self.session.external_driver)
        self.notify("Draft updated. Press Ctrl+S to apply.", severity="warning")

    def action_apply_changes(self) -> None:
        """Persist draft changes to disk."""
        if not self.session.has_changes():
            self.notify("No pending changes to apply.", severity="information")
            return

        self.state.replace_state(self.session.raw)
        self.state.reload()
        self.session.reset()

        if self.session.proxy_mode == "system":
            from devhost_cli.caddy_lifecycle import write_system_caddyfile

            write_system_caddyfile(self.state)
        elif self.session.proxy_mode == "external":
            from devhost_cli.proxy import export_snippets

            export_snippets(self.state, [self.session.external_driver])

        self.notify("Changes applied.", severity="information")
        self.refresh_data()

    def action_emergency_reset(self) -> None:
        """Emergency reset - kill owned processes only."""
        from .modals import ConfirmResetModal

        self.push_screen(ConfirmResetModal())

    def action_external_proxy(self) -> None:
        """Open external proxy attach/detach flow."""
        from .modals import ExternalProxyModal

        self.push_screen(ExternalProxyModal())

    def action_add_route(self) -> None:
        """Show add route wizard."""
        from .modals import AddRouteWizard

        self._ensure_port_scan()
        ports, in_progress = self.get_port_scan_results()
        self.push_screen(AddRouteWizard(detected_ports=ports, scan_in_progress=in_progress))

    def action_delete_route(self) -> None:
        """Delete selected route."""
        if self.selected_route:
            self.session.remove_route(self.selected_route)
            self.notify(f"Removed route: {self.selected_route} (draft)", severity="information")
            self._probe_results.pop(self.selected_route, None)
            self._log_buffers.pop(self.selected_route, None)
            self.selected_route = None
            self.refresh_data()

    def action_open_url(self) -> None:
        """Open selected route URL in browser."""
        if self.selected_route:
            import webbrowser

            route = self.session.get_route(self.selected_route)
            if route:
                domain = route.get("domain", self.session.system_domain)
                mode = self.session.proxy_mode
                if mode == "gateway":
                    url = f"http://{self.selected_route}.{domain}:{self.session.gateway_port}"
                elif mode == "system":
                    url = f"http://{self.selected_route}.{domain}"
                else:
                    url = f"http://{self.selected_route}.{domain}"
                webbrowser.open(url)
                self.notify(f"Opened: {url}", severity="information")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle route selection in the grid."""
        if event.data_table.id != "routes-table":
            return
        # Get route name from the selected row
        row_key = event.row_key
        if row_key:
            # The row key is the route name
            self.selected_route = str(row_key.value)
            details = self.query_one(DetailsPane)
            route = self.session.get_route(self.selected_route)
            if route:
                details.show_route(
                    self.selected_route,
                    route,
                    self.session,
                    self._probe_results,
                    self._integrity_results if self._integrity_results else None,
                    self.state,
                )
            self._refresh_logs_view()
            if self._log_tail_enabled:
                self._log_tail_worker(self.selected_route)


def run_dashboard():
    """Run the Devhost dashboard."""
    app = DevhostDashboard()
    app.run()


if __name__ == "__main__":
    run_dashboard()
