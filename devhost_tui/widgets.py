"""
Devhost TUI - Custom Widgets

Contains the custom widgets for the dashboard:
- NavSidebar: Vertical ListView navigation with icons
- StatusGrid: Route status table
- DetailsPane: Tabbed details view (flow, verify, logs, config, integrity)
- FlowDiagram: ASCII traffic flow visualization
- IntegrityPanel: File integrity status
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
)

from devhost_cli.state import StateConfig

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Navigation Items
# ---------------------------------------------------------------------------

NAV_ITEMS = [
    ("routes", "📋", "Routes"),
    ("tunnels", "🔗", "Tunnels"),
    ("proxy", "⚙", "Proxy"),
    ("diagnostics", "🩺", "Diagnostics"),
    ("settings", "🔧", "Settings"),
]


# ---------------------------------------------------------------------------
# NavSidebar
# ---------------------------------------------------------------------------


class NavSidebar(Static):
    """Vertical sidebar with icon-labelled navigation and state summary."""

    class ScreenSelected(Message):
        """Posted when the user selects a nav item."""

        def __init__(self, screen_id: str) -> None:
            self.screen_id = screen_id
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active: str = "routes"
        self._state: StateConfig | None = None

    def compose(self) -> ComposeResult:
        yield Static("[bold cyan]Devhost[/] Dashboard", id="app-title")
        yield ListView(
            *[ListItem(Static(f"{icon}  {label}"), id=f"nav-{sid}") for sid, icon, label in NAV_ITEMS],
            id="nav-list",
        )
        yield Static("", id="ownership-banner")

    def on_mount(self) -> None:
        self._highlight_active()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id
        if item_id and item_id.startswith("nav-"):
            screen_id = item_id.removeprefix("nav-")
            self._active = screen_id
            self._highlight_active()
            self.post_message(self.ScreenSelected(screen_id))

    def _highlight_active(self) -> None:
        nav_list = self.query_one("#nav-list", ListView)
        for item in nav_list.children:
            if hasattr(item, "id") and item.id:
                sid = item.id.removeprefix("nav-")
                if sid == self._active:
                    item.add_class("active")
                else:
                    item.remove_class("active")

    def set_active(self, screen_id: str) -> None:
        self._active = screen_id
        if self.is_mounted:
            self._highlight_active()

    def update_state(
        self,
        state: StateConfig | None = None,
        integrity_results: dict | None = None,
        system_info: dict | None = None,
    ) -> None:
        """Update sidebar with current state summary."""
        self._state = state
        banner = self.query_one("#ownership-banner", Static)
        if not state:
            banner.update("")
            return
        mode = state.proxy_mode
        if mode == "external":
            owner_text = f"[yellow]External proxy[/yellow] • {state.external_driver}"
        elif mode == "system":
            owner_text = "[green]System proxy (owned)[/green]"
        elif mode == "gateway":
            owner_text = "[green]Gateway (owned)[/green]"
        elif mode == "off":
            owner_text = "[dim]Proxy off[/dim]"
        else:
            owner_text = "[dim]Unknown[/dim]"
        banner.update(owner_text)


# ---------------------------------------------------------------------------
# StatusGrid
# ---------------------------------------------------------------------------


class StatusGrid(Static):
    """Main status grid showing all routes."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._routes: dict = {}
        self._mode: str = "gateway"
        self._domain: str = "localhost"
        self._gateway_port: int = 7777

    def compose(self) -> ComposeResult:
        yield Label("[b]Routes[/b]", classes="section-title")
        yield DataTable(id="routes-table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_column("Name", key="name", width=18)
        table.add_column("Domain", key="domain", width=30)
        table.add_column("Target", key="target", width=25)
        table.add_column("Status", key="status", width=14)
        table.add_column("Latency", key="latency", width=10)

    def update_routes(
        self,
        routes: dict,
        mode: str,
        domain: str,
        gateway_port: int,
        probe_results: dict | None = None,
        integrity_ok: bool | None = None,
    ) -> None:
        self._routes = routes
        self._mode = mode
        self._domain = domain
        self._gateway_port = gateway_port

        table = self.query_one(DataTable)
        table.clear()

        if not routes:
            table.add_row("No routes configured", "", "", "", "", key="empty")
            return

        for name, route in routes.items():
            enabled = route.get("enabled", True)
            upstream = route.get("upstream", "unknown")
            route_domain = route.get("domain", domain)

            if mode == "gateway":
                domain_display = f"{name}.{route_domain}:{gateway_port}"
            else:
                domain_display = f"{name}.{route_domain}"

            route_healthy = enabled
            latency_display = "-"
            if enabled and probe_results:
                result = probe_results.get(name)
                if result:
                    route_ok = result.get("route_ok")
                    upstream_ok = result.get("upstream_ok")
                    latency = result.get("latency_ms")
                    if latency is not None:
                        latency_display = f"{latency:.0f}ms"
                    route_healthy = route_ok is True and upstream_ok is not False

            if not enabled:
                status_str = "[dim]● DISABLED[/dim]"
            elif route_healthy:
                status_str = "[green]● ONLINE[/green]"
            else:
                status_str = "[red]● OFFLINE[/red]"

            table.add_row(name, domain_display, upstream, status_str, latency_display, key=name)


# ---------------------------------------------------------------------------
# FlowDiagram
# ---------------------------------------------------------------------------


class FlowDiagram(Static):
    """ASCII traffic flow visualization."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._route_name: str = ""
        self._route: dict = {}
        self._mode: str = "gateway"

    def compose(self) -> ComposeResult:
        yield Markdown("", id="flow-content")

    def show_flow(self, name: str, route: dict, mode: str, domain: str, gateway_port: int) -> None:
        self._route_name = name
        self._route = route
        self._mode = mode

        upstream = route.get("upstream", "127.0.0.1:8000")
        route_domain = route.get("domain", domain)
        host = f"{name}.{route_domain}"

        diagrams = {
            "off": f"**Mode:** Awareness (off)\n\n"
            f"    [Browser] ──({upstream.split(':')[-1]})──> [App: {name}]\n"
            f"         │                                │\n"
            f"         └── Direct connection ───────────┘\n",
            "gateway": f"**Mode:** Gateway (port {gateway_port})\n\n"
            f"    [Browser] ──({gateway_port})──> [Devhost] ──({upstream})──> [App: {name}]\n"
            f"         │                  │                   │\n"
            f"      Request          Route lookup         Upstream\n"
            f"    Host: {host}\n",
            "system": f"**Mode:** System (port 80/443)\n\n"
            f"    [Browser] ──(80)──> [Devhost Caddy] ──({upstream})──> [App: {name}]\n"
            f"         │                    │                   │\n"
            f"      Request            TLS + Route          Upstream\n"
            f"    Host: {host}\n",
            "external": f"**Mode:** External\n\n"
            f"    [Browser] ──(80)──> [External Proxy] ──({upstream})──> [App: {name}]\n"
            f"         │                     │                      │\n"
            f"      Request            User-managed            Upstream\n"
            f"    Host: {host}\n",
        }
        diagram = diagrams.get(mode, "Unknown mode")
        self.query_one("#flow-content", Markdown).update(diagram)


# ---------------------------------------------------------------------------
# IntegrityPanel
# ---------------------------------------------------------------------------


class IntegrityPanel(Static):
    """File integrity status panel."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._state: StateConfig | None = None
        self._results: dict[str, tuple[bool, str]] = {}
        self._selected_path: str | None = None

    def compose(self) -> ComposeResult:
        yield Label("[b]Integrity Status[/b]", classes="section-title")
        yield DataTable(id="integrity-table")
        yield Static(
            "[dim]Accept: Update hash • Stop: Remove tracking • Diff: View changes • Restore: Revert[/dim]",
            id="integrity-button-help",
        )
        with Horizontal(id="integrity-actions"):
            yield Button("Accept", id="integrity-accept", variant="success")
            yield Button("Stop Tracking", id="integrity-ignore", variant="warning")
            yield Button("View Diff", id="integrity-diff", variant="default")
            yield Button("Restore Backup", id="integrity-restore", variant="warning")
            yield Button("Cancel", id="integrity-cancel", variant="default")
        yield Static("Select a file to resolve drift.", id="integrity-help")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("File", width=50)
        table.add_column("Status", width=15)
        table.cursor_type = "row"
        table.zebra_stripes = True

    def _update_help(self, message: str) -> None:
        self.query_one("#integrity-help", Static).update(message)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key
        self._selected_path = str(row_key.value) if row_key else None
        if self._selected_path:
            self._update_help(f"Selected: {self._selected_path}")
        else:
            self._update_help("Select a file to resolve drift.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "integrity-accept":
            self._resolve_selected("accept")
        elif event.button.id == "integrity-ignore":
            self._resolve_selected("ignore")
        elif event.button.id == "integrity-diff":
            if not self._selected_path:
                if hasattr(self.app, "notify"):
                    self.app.notify("Select a file to diff first.", severity="warning")
                return
            if hasattr(self.app, "show_integrity_diff"):
                self.app.show_integrity_diff(self._selected_path)
        elif event.button.id == "integrity-restore":
            if not self._selected_path:
                if hasattr(self.app, "notify"):
                    self.app.notify("Select a file to restore first.", severity="warning")
                return
            if hasattr(self.app, "restore_integrity_backup"):
                self.app.restore_integrity_backup(self._selected_path)
        elif event.button.id == "integrity-cancel":
            self._selected_path = None
            self._update_help("Resolution cancelled.")

    def _resolve_selected(self, action: str) -> None:
        if not self._selected_path:
            if hasattr(self.app, "notify"):
                self.app.notify("Select a file to resolve first.", severity="warning")
            return
        if not self._state:
            if hasattr(self.app, "notify"):
                self.app.notify("Integrity state unavailable.", severity="error")
            return
        resolver = getattr(self.app, "resolve_integrity", None)
        if not callable(resolver):
            if hasattr(self.app, "notify"):
                self.app.notify("Integrity resolution not supported.", severity="error")
            return
        resolver(self._selected_path, action)
        self._selected_path = None

    def update_integrity(self, state: StateConfig, results: dict | None = None) -> None:
        self._state = state
        table = self.query_one(DataTable)
        table.clear()

        results = results if results is not None else state.check_all_integrity()
        self._results = results
        self._selected_path = None

        if not results:
            self._update_help("No tracked files for integrity.")
        else:
            issues = [path for path, (ok, _) in results.items() if not ok]
            if issues:
                self._update_help("Select a drifted file to resolve.")
            else:
                self._update_help("No integrity issues detected.")

        for filepath, (ok, status) in results.items():
            short_path = filepath.replace(str(state.devhost_dir), "~/.devhost")
            status_display = f"[green]{status}[/]" if ok else f"[red]{status}[/]"
            table.add_row(short_path, status_display, key=filepath)


# ---------------------------------------------------------------------------
# DetailsPane
# ---------------------------------------------------------------------------


class DetailsPane(Static):
    """Tabbed details pane showing route information."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_route: str | None = None
        self._current_route_data: dict = {}
        self._state: StateConfig | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="route-actions"):
            yield Button("Open", id="route-open")
            yield Button("Copy URL", id="route-copy-url")
            yield Button("Copy Host", id="route-copy-host")
            yield Button("Copy Upstream", id="route-copy-upstream")
        with TabbedContent():
            with TabPane("Flow", id="tab-flow"):
                yield FlowDiagram(id="flow-diagram")
            with TabPane("Verify", id="tab-verify"):
                yield Static("Select a route to verify", id="verify-content")
            with TabPane("Logs", id="tab-logs"):
                yield Label("Filter:", classes="field-label")
                yield Input(placeholder="Filter logs (case-insensitive)", id="logs-filter")
                with Horizontal(id="logs-actions"):
                    yield Button("Apply Filter", id="logs-filter-apply")
                    yield Button("Clear Filter", id="logs-filter-clear")
                    yield Button("Copy Visible", id="logs-copy")
                yield Label("Levels:", classes="field-label")
                with Horizontal(id="logs-levels"):
                    yield Button("All", id="logs-level-all", classes="log-level-btn")
                    yield Button("Info", id="logs-level-info", classes="log-level-btn")
                    yield Button("Warn", id="logs-level-warn", classes="log-level-btn")
                    yield Button("Error", id="logs-level-error", classes="log-level-btn")
                yield Static("", id="logs-content")
            with TabPane("Config", id="tab-config"):
                with VerticalScroll(id="config-scroll"):
                    yield Markdown("", id="config-content")
            with TabPane("Integrity", id="tab-integrity"):
                yield IntegrityPanel(id="integrity-panel")

    def show_route(
        self,
        name: str,
        route: dict,
        state,
        probe_results: dict | None = None,
        integrity_results: dict | None = None,
        integrity_state: StateConfig | None = None,
    ) -> None:
        self._current_route = name
        self._current_route_data = route
        self._state = state

        # Flow diagram
        flow = self.query_one(FlowDiagram)
        flow.show_flow(name, route, state.proxy_mode, state.system_domain, state.gateway_port)

        # Verify tab
        verify = self.query_one("#verify-content", Static)
        upstream = route.get("upstream", "unknown")
        upstreams = route.get("upstreams")
        upstream_display = upstream
        if isinstance(upstreams, list) and upstreams:
            formatted = []
            for entry in upstreams:
                if isinstance(entry, dict):
                    entry_type = str(entry.get("type", "tcp"))
                    entry_target = str(entry.get("target", "")).strip()
                    formatted.append(
                        f"{entry_type}:{entry_target}" if entry_type != "tcp" else entry_target or "unknown"
                    )
                else:
                    formatted.append(str(entry))
            upstream_display = ", ".join(formatted) if formatted else upstream

        probe = probe_results.get(name) if probe_results else None
        if probe:
            route_ok = probe.get("route_ok")
            upstream_ok = probe.get("upstream_ok")
            latency = probe.get("latency_ms")
            last_checked = probe.get("checked_at")
            route_error = probe.get("route_error")
            upstream_error = probe.get("upstream_error")
            route_scheme = probe.get("route_scheme")
            route_port = probe.get("route_port")
            latency_text = f"{latency:.0f}ms" if latency is not None else "-"
            status_line = "OK" if route_ok else "FAIL" if route_ok is False else "UNKNOWN"
            upstream_line = "OK" if upstream_ok else "FAIL" if upstream_ok is False else "UNKNOWN"
            lines = [
                f"Route: {name}",
                f"Upstream: {upstream_display}",
                f"Upstream TCP: {upstream_line}",
                f"Route Probe: {status_line}",
            ]
            if route_scheme and route_port:
                lines.append(f"Probe Target: {route_scheme}://127.0.0.1:{route_port}")
            lines.extend([f"Latency: {latency_text}", f"Last Checked: {last_checked or '-'}"])
            if upstream_error:
                lines.append(f"Upstream Error: {upstream_error}")
            if route_error:
                lines.append(f"Route Error: {route_error}")
            if integrity_results:
                drift = [path for path, (ok, _) in integrity_results.items() if not ok]
                if drift:
                    lines.append(f"Integrity: DRIFT ({len(drift)} files)")
                    for path in drift[:3]:
                        lines.append(f"  - {path}")
                else:
                    lines.append("Integrity: OK")
            verify.update("\n".join(lines))
        else:
            verify.update(f"Route: {name}\nUpstream: {upstream_display}\n\nPress Ctrl+P to probe")

        # Config tab
        config = self.query_one("#config-content", Markdown)
        domain = route.get("domain", state.system_domain)
        enabled = route.get("enabled", True)
        persisted = integrity_state or StateConfig()
        external_driver = getattr(state, "external_driver", None) or getattr(persisted, "external_driver", "caddy")
        external_config = getattr(state, "external_config_path", None) or getattr(
            persisted, "external_config_path", None
        )
        external_path = str(external_config) if external_config else "Not set"
        snippet_driver = "caddy" if state.proxy_mode != "external" else external_driver
        snippet_content = ""
        try:
            from devhost_cli.proxy import generate_snippet, route_spec_from_dict

            default_domain = (integrity_state or state).system_domain
            route_spec = route_spec_from_dict(name, route, default_domain)
            snippet_content = generate_snippet(snippet_driver, [route_spec])
        except Exception:
            snippet_content = f"# Unable to generate {snippet_driver} snippet"
        config.update(
            f"## Route Configuration\n\n"
            f"**Name:** `{name}`\n"
            f"**Upstream:** `{upstream_display}`\n"
            f"**Domain:** `{domain}`\n"
            f"**Enabled:** `{enabled}`\n\n"
            f"### External Proxy\n"
            f"**Driver:** `{external_driver}`\n"
            f"**Config Path:** `{external_path}`\n\n"
            f"### Generated {snippet_driver.capitalize()} Snippet\n```\n{snippet_content}\n```\n"
        )

        # Integrity panel
        integrity = self.query_one(IntegrityPanel)
        integrity.update_integrity(integrity_state or state, integrity_results)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_to_action = {
            "route-open": "action_open_url",
            "route-copy-url": "action_copy_url",
            "route-copy-host": "action_copy_host",
            "route-copy-upstream": "action_copy_upstream",
            "logs-filter-apply": None,
            "logs-filter-clear": None,
            "logs-copy": None,
            "logs-level-all": None,
            "logs-level-info": None,
            "logs-level-warn": None,
            "logs-level-error": None,
        }

        bid = event.button.id
        if bid in ("route-open", "route-copy-url", "route-copy-host", "route-copy-upstream"):
            action = button_to_action[bid]
            if action and hasattr(self.app, action):
                getattr(self.app, action)()
        elif bid == "logs-filter-apply":
            if hasattr(self.app, "set_log_filter"):
                self.app.set_log_filter(self.query_one("#logs-filter", Input).value)
        elif bid == "logs-filter-clear":
            if hasattr(self.app, "clear_log_filter"):
                self.app.clear_log_filter()
        elif bid == "logs-copy":
            if hasattr(self.app, "copy_logs"):
                self.app.copy_logs()
        elif bid in ("logs-level-all", "logs-level-info", "logs-level-warn", "logs-level-error"):
            level_map = {
                "logs-level-all": lambda: self.app.set_log_levels({"info", "warn", "error"}),
                "logs-level-info": lambda: self.app.toggle_log_level("info"),
                "logs-level-warn": lambda: self.app.toggle_log_level("warn"),
                "logs-level-error": lambda: self.app.toggle_log_level("error"),
            }
            fn = level_map.get(bid)
            if fn and hasattr(self.app, "set_log_levels"):
                fn()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "logs-filter" and hasattr(self.app, "set_log_filter"):
            self.app.set_log_filter(event.value)

    def update_log_level_buttons(self, active: set[str]) -> None:
        try:
            info_btn = self.query_one("#logs-level-info", Button)
            warn_btn = self.query_one("#logs-level-warn", Button)
            error_btn = self.query_one("#logs-level-error", Button)
            all_btn = self.query_one("#logs-level-all", Button)
        except Exception:
            return

        def _set(btn: Button, enabled: bool) -> None:
            btn.variant = "success" if enabled else "default"

        _set(info_btn, "info" in active)
        _set(warn_btn, "warn" in active)
        _set(error_btn, "error" in active)
        _set(all_btn, active == {"info", "warn", "error"})
