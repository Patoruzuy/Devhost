"""
Devhost TUI - Main Application

Slim shell that composes:
- NavSidebar for screen switching
- ContentSwitcher to keep all screens mounted
- StateWatcher / ProbeService / LogTailService for background work
- Built-in CommandPalette via DevhostCommandProvider
"""

from __future__ import annotations

import difflib
import shutil
import time
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import ContentSwitcher, Footer, Header, Static

from devhost_cli.scanner import ListeningPort
from devhost_cli.state import StateConfig
from devhost_cli.validation import get_dev_scheme

from .commands import DevhostCommandProvider
from .screens import DiagnosticsScreen, ProxyScreen, RoutesScreen, SettingsScreen, TunnelsScreen
from .services import (
    LogTailService,
    PortScanCache,
    PortScanComplete,
    ProbeComplete,
    ProbeService,
    StateFileChanged,
    StateWatcher,
)
from .session import SessionState
from .widgets import NavSidebar


class DevhostDashboard(App):
    """The main Devhost TUI application."""

    TITLE = "Devhost Dashboard"
    SUB_TITLE = "Local Development Router"
    COMMANDS = {DevhostCommandProvider}

    CSS = """
    Screen {
        layout: horizontal;
    }

    #sidebar {
        width: 26;
        background: $surface;
        border-right: solid $primary;
        padding: 1;
    }

    #sidebar #app-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #sidebar #nav-list {
        height: auto;
    }

    #sidebar #nav-list ListItem {
        padding: 0 1;
        height: 3;
    }

    #sidebar #nav-list ListItem.active {
        background: $primary-darken-2;
    }

    #sidebar #ownership-banner {
        margin-top: 1;
        padding: 0 1;
        background: $surface-darken-1;
        border: round $primary-darken-2;
    }

    #main-area {
        width: 1fr;
    }

    #main-area ContentSwitcher {
        width: 100%;
        height: 1fr;
    }

    #screen-routes, #screen-tunnels, #screen-proxy,
    #screen-diagnostics, #screen-settings {
        width: 100%;
        height: 100%;
        padding: 1;
    }

    #draft-banner {
        dock: bottom;
        height: 3;
        background: $warning-darken-2;
        border-top: double $warning;
        padding: 1;
        display: none;
    }

    #draft-banner.visible {
        display: block;
    }

    .section-title {
        text-style: bold;
        color: $text;
        padding: 0 1;
        margin-bottom: 1;
    }

    StatusGrid {
        height: auto;
        max-height: 50%;
    }

    StatusGrid > DataTable {
        height: 100%;
    }

    .status-ok { color: $success; }
    .status-warning { color: $warning; }
    .status-error { color: $error; }

    Input:focus {
        border: double $success;
    }
    Button:focus {
        text-style: bold reverse;
    }
    """

    BINDINGS = [
        Binding("f1", "show_help", "Help", show=True, priority=True),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("ctrl+i", "integrity_check", "Integrity"),
        Binding("ctrl+p", "probe_routes", "Probe"),
        Binding("ctrl+s", "apply_changes", "Apply"),
        Binding("ctrl+b", "export_diagnostics", "Bundle"),
        Binding("ctrl+q", "show_qr", "QR Code", show=True, priority=True),
        Binding("ctrl+a", "add_route", "Add Route"),
        Binding("ctrl+d", "delete_route", "Delete Route"),
        Binding("ctrl+o", "open_url", "Open URL"),
        Binding("ctrl+x", "emergency_reset", "Emergency Reset"),
        Binding("ctrl+y", "copy_url", "Copy URL"),
        Binding("ctrl+h", "copy_host", "Copy Host"),
        Binding("ctrl+u", "copy_upstream", "Copy Upstream"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.state = StateConfig()
        self.session = SessionState(self.state)
        self.selected_route: str | None = None
        self._probe_results: dict[str, dict] = {}
        self._integrity_results: dict[str, tuple[bool, str]] | None = None
        self._log_filter = ""
        self._log_levels: set[str] = {"info", "warn", "error"}
        self._last_probe_time: float | None = None

        # Services (initialized on_mount)
        self._state_watcher: StateWatcher | None = None
        self._probe_service: ProbeService | None = None
        self._log_service: LogTailService | None = None
        self._port_scan: PortScanCache | None = None

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield NavSidebar(id="sidebar")
            with ContentSwitcher(initial="screen-routes", id="main-area"):
                yield RoutesScreen(id="screen-routes")
                yield TunnelsScreen(id="screen-tunnels")
                yield ProxyScreen(id="screen-proxy")
                yield DiagnosticsScreen(id="screen-diagnostics")
                yield SettingsScreen(id="screen-settings")
        yield Static("", id="draft-banner")
        yield Footer()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self._state_watcher = StateWatcher(self)
        self._probe_service = ProbeService(self)
        self._log_service = LogTailService(self)
        self._port_scan = PortScanCache(self)

        self._state_watcher.start()
        self._probe_service.start()
        self._log_service.start()
        self.refresh_data()

    def on_unmount(self) -> None:
        if self._state_watcher:
            self._state_watcher.stop()

    # ------------------------------------------------------------------
    # Screen switching
    # ------------------------------------------------------------------

    def on_nav_sidebar_screen_selected(self, event: NavSidebar.ScreenSelected) -> None:
        self.switch_screen_by_id(event.screen_id)

    def switch_screen_by_id(self, screen_id: str) -> None:
        """Switch the active screen in the ContentSwitcher."""
        switcher = self.query_one(ContentSwitcher)
        target = f"screen-{screen_id}"
        switcher.current = target
        sidebar = self.query_one(NavSidebar)
        sidebar.set_active(screen_id)

    # ------------------------------------------------------------------
    # State watcher callback
    # ------------------------------------------------------------------

    def on_state_file_changed(self, _event: StateFileChanged) -> None:
        """Handle state.yml changes detected by watchdog/polling."""
        if self.session.has_changes():
            self.notify("State updated on disk. Apply or discard your draft to sync.", severity="warning")
        else:
            self.session.reset()
            self.refresh_data()

    # ------------------------------------------------------------------
    # Probe service callback
    # ------------------------------------------------------------------

    def on_probe_complete(self, event: ProbeComplete) -> None:
        self._probe_results = event.results
        self._last_probe_time = time.time()
        self.refresh_data()

    # ------------------------------------------------------------------
    # Port scan callback
    # ------------------------------------------------------------------

    def on_port_scan_complete(self, event: PortScanComplete) -> None:
        from .wizard import AddRouteWizard

        for screen in reversed(self.screen_stack):
            if isinstance(screen, AddRouteWizard):
                screen.set_detected_ports(event.ports)
                break

    def get_port_scan_results(self) -> tuple[list[ListeningPort], bool]:
        if self._port_scan:
            return self._port_scan.get_results()
        return [], False

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def refresh_data(self) -> None:
        """Refresh all displayed data from state."""
        self.state.reload()
        if not self.session.has_changes():
            self.session.reset()

        if self._integrity_results is None:
            self._integrity_results = self.state.check_all_integrity()

        # Refresh the routes screen (primary view)
        try:
            routes_screen = self.query_one("#screen-routes", RoutesScreen)
            routes_screen.refresh_data(
                session=self.session,
                probe_results=self._probe_results,
                integrity_results=self._integrity_results,
                state=self.state,
            )
        except Exception:
            pass

        # Update sidebar state
        try:
            sidebar = self.query_one(NavSidebar)
            sidebar.update_state(self.state, self._integrity_results)
        except Exception:
            pass

        self._update_draft_banner()

    def _update_draft_banner(self) -> None:
        try:
            banner = self.query_one("#draft-banner", Static)
        except Exception:
            return
        if self.session.has_changes():
            banner.add_class("visible")
            banner.update(
                "[b]⚠️  DRAFT MODE:[/b] You have unsaved changes. Press [b]Ctrl+S[/b] to apply or restart to discard."
            )
        else:
            banner.remove_class("visible")

    # ------------------------------------------------------------------
    # Probing
    # ------------------------------------------------------------------

    def _schedule_probe(self) -> None:
        if self._probe_service:
            self._probe_service.probe()

    # ------------------------------------------------------------------
    # Route info helpers
    # ------------------------------------------------------------------

    def _get_route_info(self) -> tuple[str, str, str] | None:
        if not self.selected_route:
            self.notify("Select a route first.", severity="warning")
            return None
        route = self.session.get_route(self.selected_route)
        if not route:
            self.notify("Route not found.", severity="error")
            return None
        domain = route.get("domain", self.session.system_domain)
        mode = self.session.proxy_mode
        upstream = route.get("upstream", "")
        if mode == "gateway":
            url = f"http://{self.selected_route}.{domain}:{self.session.gateway_port}"
        else:
            scheme = get_dev_scheme(upstream)
            url = f"{scheme}://{self.selected_route}.{domain}"
        host_header = f"{self.selected_route}.{domain}"
        return url, host_header, upstream

    def _copy_to_clipboard(self, text: str) -> bool:
        try:
            if hasattr(self, "copy_to_clipboard"):
                self.copy_to_clipboard(text)
                return True
        except Exception:
            return False
        return False

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_refresh(self) -> None:
        self.refresh_data()
        self.notify("Data refreshed", severity="information")

    def action_integrity_check(self) -> None:
        results = self.state.check_all_integrity()
        self._integrity_results = results
        self.refresh_data()
        issues = [p for p, (ok, _) in results.items() if not ok]
        if issues:
            self.notify(f"Integrity issues found: {len(issues)} files", severity="warning")
        else:
            self.notify("All files OK", severity="information")

    def action_probe_routes(self) -> None:
        self.notify("Probing routes...", severity="information")
        self._schedule_probe()

    def action_apply_changes(self) -> None:
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

    def action_add_route(self) -> None:
        from .wizard import AddRouteWizard

        if self._port_scan:
            self._port_scan.ensure_scan()
        ports, in_progress = self.get_port_scan_results()
        self.push_screen(AddRouteWizard(detected_ports=ports, scan_in_progress=in_progress))

    def action_delete_route(self) -> None:
        if not self.selected_route:
            self.notify("Select a route first.", severity="warning")
            return
        from .modals import ConfirmDeleteModal

        def _on_confirm(confirmed: bool) -> None:
            if confirmed and self.selected_route:
                name = self.selected_route
                self.session.remove_route(name)
                self._probe_results.pop(name, None)
                self.selected_route = None
                self.notify(f"Removed route: {name} (draft)", severity="information")
                self.refresh_data()

        self.push_screen(ConfirmDeleteModal(self.selected_route), _on_confirm)

    def action_open_url(self) -> None:
        info = self._get_route_info()
        if info:
            import webbrowser

            url, _, _ = info
            webbrowser.open(url)
            self.notify(f"Opened: {url}", severity="information")

    def action_copy_url(self) -> None:
        info = self._get_route_info()
        if not info:
            return
        url, _, _ = info
        if self._copy_to_clipboard(url):
            self.notify("URL copied to clipboard.", severity="information")
        else:
            self.notify("Clipboard unavailable.", severity="warning")

    def action_copy_host(self) -> None:
        info = self._get_route_info()
        if not info:
            return
        _, host, _ = info
        if self._copy_to_clipboard(host):
            self.notify("Host copied to clipboard.", severity="information")
        else:
            self.notify("Clipboard unavailable.", severity="warning")

    def action_copy_upstream(self) -> None:
        info = self._get_route_info()
        if not info:
            return
        _, _, upstream = info
        if self._copy_to_clipboard(upstream):
            self.notify("Upstream copied to clipboard.", severity="information")
        else:
            self.notify("Clipboard unavailable.", severity="warning")

    def action_show_help(self) -> None:
        from .modals import HelpModal

        self.push_screen(HelpModal())

    def action_show_qr(self) -> None:
        info = self._get_route_info()
        if not info:
            return
        url, _, _ = info
        from .modals import QRCodeModal

        self.push_screen(QRCodeModal(self.selected_route, url))

    def action_emergency_reset(self) -> None:
        from .modals import ConfirmResetModal

        self.push_screen(ConfirmResetModal())

    def action_export_diagnostics(self) -> None:
        self.notify("Building diagnostic bundle (redacted)...", severity="information")
        self._export_diagnostics_worker(redact=True)

    def export_diagnostics(self, redact: bool = True) -> None:
        """Export diagnostic bundle (callable from command palette)."""
        label = "redacted" if redact else "raw"
        self.notify(f"Building diagnostic bundle ({label})...", severity="information")
        self._export_diagnostics_worker(redact=redact)

    # ------------------------------------------------------------------
    # Diagnostics workers
    # ------------------------------------------------------------------

    @work(exclusive=True, thread=True)
    def _export_diagnostics_worker(self, redact: bool = True) -> None:
        from devhost_cli.diagnostics import export_diagnostic_bundle

        success, bundle_path, manifest = export_diagnostic_bundle(self.state, redact=redact)
        self.call_from_thread(self._export_diagnostics_done, success, bundle_path, manifest)

    def _export_diagnostics_done(self, success: bool, bundle_path: Path | None, manifest: dict) -> None:
        if success and bundle_path:
            count = len(manifest.get("included", []))
            redacted = len(manifest.get("redacted", []))
            self.notify(
                f"Diagnostic bundle saved: {bundle_path} ({count} files, {redacted} redacted)",
                severity="information",
            )
        else:
            error = manifest.get("error", "unknown error")
            self.notify(f"Diagnostic bundle failed: {error}", severity="error")

    # ------------------------------------------------------------------
    # Integrity helpers
    # ------------------------------------------------------------------

    def resolve_integrity(self, filepath: str, action: str) -> None:
        path = Path(filepath)
        if action == "accept":
            if not path.exists():
                self.notify("File is missing. Cannot accept.", severity="error")
                return
            self.state.record_hash(path)
            msg = "Integrity updated to match current file."
        elif action == "ignore":
            self.state.remove_hash(path)
            msg = "Stopped tracking file integrity."
        else:
            return
        self._integrity_results = self.state.check_all_integrity()
        self.refresh_data()
        self.notify(msg, severity="information")

    def show_integrity_diff(self, filepath: str) -> None:
        from .modals import IntegrityDiffModal

        path = Path(filepath)
        backup = self._latest_backup_for(path)
        if not backup:
            self.notify("No backup found to diff.", severity="warning")
            return
        try:
            backup_text = backup.read_text(encoding="utf-8", errors="replace").splitlines()
            current_text = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
            diff_lines = list(
                difflib.unified_diff(backup_text, current_text, fromfile=str(backup), tofile=str(path), lineterm="")
            )
        except OSError as exc:
            self.notify(f"Failed to read files: {exc}", severity="error")
            return
        if not diff_lines:
            diff_text = "No differences detected."
        else:
            if len(diff_lines) > 400:
                diff_lines = diff_lines[:400] + ["... (truncated)"]
            diff_text = "\n".join(diff_lines)
        self.push_screen(IntegrityDiffModal(diff_text))

    def restore_integrity_backup(self, filepath: str) -> None:
        from .modals import ConfirmRestoreModal

        path = Path(filepath)
        backup = self._latest_backup_for(path)
        if not backup:
            self.notify("No backup found to restore.", severity="warning")
            return
        self.push_screen(ConfirmRestoreModal(path, backup))

    def perform_restore(self, target: Path, backup: Path) -> None:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
            self.state.record_hash(target)
            self._integrity_results = self.state.check_all_integrity()
            self.refresh_data()
            self.notify("Backup restored and integrity updated.", severity="information")
        except OSError as exc:
            self.notify(f"Restore failed: {exc}", severity="error")

    def _latest_backup_for(self, filepath: Path) -> Path | None:
        backup_dir = self.state.devhost_dir / "backups"
        if not backup_dir.exists():
            return None
        prefix = f"{filepath.name}."
        candidates = [
            p for p in backup_dir.iterdir() if p.is_file() and p.name.startswith(prefix) and p.name.endswith(".bak")
        ]
        return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None

    # ------------------------------------------------------------------
    # Log helpers (delegated to LogTailService mostly)
    # ------------------------------------------------------------------

    def set_log_filter(self, value: str) -> None:
        self._log_filter = value.strip()
        if self._log_service:
            self._log_service.text_filter = self._log_filter

    def clear_log_filter(self) -> None:
        self._log_filter = ""
        if self._log_service:
            self._log_service.text_filter = ""

    def set_log_levels(self, levels: set[str]) -> None:
        self._log_levels = set(levels)
        if self._log_service:
            self._log_service.level_filter = self._log_levels

    def toggle_log_level(self, level: str) -> None:
        if level in self._log_levels:
            self._log_levels.discard(level)
        else:
            self._log_levels.add(level)
        if not self._log_levels:
            self._log_levels = {"info", "warn", "error"}
        self.set_log_levels(self._log_levels)

    def copy_logs(self) -> None:
        if not self._log_service or not self.selected_route:
            self.notify("No logs available to copy.", severity="warning")
            return
        lines = self._log_service.get_filtered_lines(self.selected_route)
        if not lines:
            self.notify("No logs available to copy.", severity="warning")
            return
        content = "\n".join(lines[-200:])
        if self._copy_to_clipboard(content):
            self.notify(f"Copied {min(len(lines), 200)} line(s) to clipboard.", severity="information")
        else:
            self.notify("Clipboard unavailable.", severity="warning")

    # ------------------------------------------------------------------
    # Route change (from wizard / screens)
    # ------------------------------------------------------------------

    def queue_route_change(self, name: str, upstream: str, mode: str) -> None:
        self.session.set_route(name, upstream, domain=self.session.system_domain, enabled=True)
        self.session.set_proxy_mode(mode)
        if mode == "external":
            self.session.set_external_config(self.session.external_driver)
        self.notify("Draft updated. Press Ctrl+S to apply.", severity="warning")
        self.refresh_data()

    # ------------------------------------------------------------------
    # DataTable selection (routes grid)
    # ------------------------------------------------------------------

    def on_data_table_row_selected(self, event) -> None:
        from textual.widgets import DataTable

        if not isinstance(event, DataTable.RowSelected):
            return
        if event.data_table.id != "routes-table":
            return
        row_key = event.row_key
        if row_key:
            self.selected_route = str(row_key.value)
            self.refresh_data()

    # ------------------------------------------------------------------
    # Proxy expose (from ProxyExposeModal)
    # ------------------------------------------------------------------

    def perform_proxy_expose(self, bind_target: str) -> None:
        """Update gateway/system listen to the chosen bind address."""
        gateway = self.session.raw.setdefault("proxy", {}).setdefault("gateway", {})
        old_listen = gateway.get("listen", "127.0.0.1:7777")
        _, port_str = old_listen.rsplit(":", 1) if ":" in old_listen else ("", "7777")
        gateway["listen"] = f"{bind_target}:{port_str}"

        system = self.session.raw.setdefault("proxy", {}).setdefault("system", {})
        system["listen_http"] = f"{bind_target}:80"
        system["listen_https"] = f"{bind_target}:443"

        self.notify(f"Bind updated to {bind_target}. Press Ctrl+S to apply.", severity="warning")
        self.refresh_data()


def run_dashboard() -> None:
    """Run the Devhost dashboard."""
    app = DevhostDashboard()
    app.run()


if __name__ == "__main__":
    run_dashboard()
