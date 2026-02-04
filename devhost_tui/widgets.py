"""
Devhost TUI - Custom Widgets

Contains the custom widgets for the dashboard:
- Sidebar: Navigation tree
- StatusGrid: Route status table
- DetailsPane: Tabbed details view
- FlowDiagram: ASCII traffic flow visualization
- IntegrityPanel: File integrity status
"""

from textual.app import ComposeResult
from textual.widgets import DataTable, Label, Markdown, Static, TabbedContent, TabPane, Tree

from devhost_cli.state import StateConfig


class Sidebar(Static):
    """Navigation sidebar with tree view."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._state: StateConfig | None = None

    def compose(self) -> ComposeResult:
        yield Label("[b]Navigation[/b]", classes="section-title")
        yield Tree("Devhost", id="nav-tree")

    def on_mount(self) -> None:
        """Initialize the tree structure."""
        tree = self.query_one(Tree)
        tree.root.expand()

        # Add main sections
        self._apps_node = tree.root.add("Apps", expand=True)
        self._proxy_node = tree.root.add("Proxy", expand=True)
        self._integrity_node = tree.root.add("Integrity", expand=True)
        self._system_node = tree.root.add("System", expand=True)

        # Add proxy status items
        self._proxy_node.add_leaf("Mode: gateway")
        self._proxy_node.add_leaf("Gateway: :7777")

        # Add system items
        self._system_node.add_leaf("Diagnostics")
        self._system_node.add_leaf("Settings")

    def update_state(self, state: StateConfig) -> None:
        """Update sidebar with current state."""
        self._state = state

        # Clear and rebuild apps
        self._apps_node.remove_children()
        for name, route in state.routes.items():
            enabled = route.get("enabled", True)
            status = "●" if enabled else "○"
            self._apps_node.add_leaf(f"{status} {name}")

        # Update proxy info
        self._proxy_node.remove_children()
        mode = state.proxy_mode
        self._proxy_node.add_leaf(f"Mode: {mode}")
        if mode == "gateway":
            self._proxy_node.add_leaf(f"Port: {state.gateway_port}")
        elif mode == "system":
            self._proxy_node.add_leaf("Port: 80/443")
        elif mode == "external":
            self._proxy_node.add_leaf(f"Driver: {state.external_driver}")

        # Update integrity
        self._integrity_node.remove_children()
        results = state.check_all_integrity()
        issues = sum(1 for _, (ok, _) in results.items() if not ok)
        if issues:
            self._integrity_node.add_leaf(f"⚠ {issues} issues")
        else:
            self._integrity_node.add_leaf("✓ All OK")


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
        """Initialize the data table."""
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Add columns
        table.add_column("Status", key="status", width=6)
        table.add_column("Name", key="name", width=15)
        table.add_column("Mode", key="mode", width=10)
        table.add_column("URL", key="url", width=30)
        table.add_column("Upstream", key="upstream", width=20)
        table.add_column("Integrity", key="integrity", width=10)

    def update_routes(self, routes: dict, mode: str, domain: str, gateway_port: int) -> None:
        """Update the routes table."""
        self._routes = routes
        self._mode = mode
        self._domain = domain
        self._gateway_port = gateway_port

        table = self.query_one(DataTable)
        table.clear()

        for name, route in routes.items():
            enabled = route.get("enabled", True)
            upstream = route.get("upstream", "unknown")
            route_domain = route.get("domain", domain)

            # Build URL based on mode
            if mode == "gateway":
                url = f"http://{name}.{route_domain}:{gateway_port}"
            elif mode == "system":
                url = f"http://{name}.{route_domain}"
            else:
                url = f"http://{name}.{route_domain}"

            # Status indicator
            status = "[green]●[/]" if enabled else "[dim]○[/]"

            # Mode badge
            mode_badge = f"[{mode}]"

            # Integrity (simplified)
            integrity = "[green]OK[/]"

            table.add_row(
                status,
                name,
                mode_badge,
                url,
                upstream,
                integrity,
                key=name,
            )


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
        """Display traffic flow for a route."""
        self._route_name = name
        self._route = route
        self._mode = mode

        upstream = route.get("upstream", "127.0.0.1:8000")
        route_domain = route.get("domain", domain)
        host = f"{name}.{route_domain}"

        if mode == "off":
            diagram = f"""
```
Mode: Awareness (off)

[Browser] ──({upstream.split(":")[-1]})──> [App: {name}]
    │                                │
    └── Direct connection ───────────┘
```
"""
        elif mode == "gateway":
            diagram = f"""
```
Mode: Gateway (port {gateway_port})

[Browser] ──({gateway_port})──> [Devhost Gateway] ──({upstream})──> [App: {name}]
    │                       │                      │
    Host: {host}      Route lookup           Upstream
```
"""
        elif mode == "system":
            diagram = f"""
```
Mode: System (port 80/443)

[Browser] ──(80)──> [Devhost System Proxy] ──({upstream})──> [App: {name}]
    │                       │                         │
    Host: {host}      TLS termination           Upstream
```
"""
        elif mode == "external":
            diagram = f"""
```
Mode: External

[Browser] ──(80)──> [External Proxy] ──({upstream})──> [App: {name}]
    │                     │                      │
    Host: {host}    User-managed           Upstream
```
"""
        else:
            diagram = "Unknown mode"

        content = self.query_one("#flow-content", Markdown)
        content.update(diagram)


class IntegrityPanel(Static):
    """File integrity status panel."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Label("[b]Integrity Status[/b]", classes="section-title")
        yield DataTable(id="integrity-table")

    def on_mount(self) -> None:
        """Initialize the integrity table."""
        table = self.query_one(DataTable)
        table.add_column("File", width=50)
        table.add_column("Status", width=15)

    def update_integrity(self, state: StateConfig) -> None:
        """Update integrity status."""
        table = self.query_one(DataTable)
        table.clear()

        results = state.check_all_integrity()
        for filepath, (ok, status) in results.items():
            # Shorten the path for display
            short_path = filepath.replace(str(state.devhost_dir), "~/.devhost")
            if ok:
                status_display = f"[green]{status}[/]"
            else:
                status_display = f"[red]{status}[/]"
            table.add_row(short_path, status_display)


class DetailsPane(Static):
    """Tabbed details pane showing route information."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_route: str | None = None
        self._current_route_data: dict = {}
        self._state: StateConfig | None = None

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane("Flow", id="tab-flow"):
                yield FlowDiagram(id="flow-diagram")
            with TabPane("Verify", id="tab-verify"):
                yield Static("Select a route to verify", id="verify-content")
            with TabPane("Logs", id="tab-logs"):
                yield Static("Log tailing coming soon...", id="logs-content")
            with TabPane("Config", id="tab-config"):
                yield Markdown("", id="config-content")
            with TabPane("Integrity", id="tab-integrity"):
                yield IntegrityPanel(id="integrity-panel")

    def show_route(self, name: str, route: dict, state: StateConfig) -> None:
        """Show details for a specific route."""
        self._current_route = name
        self._current_route_data = route
        self._state = state

        # Update flow diagram
        flow = self.query_one(FlowDiagram)
        flow.show_flow(name, route, state.proxy_mode, state.system_domain, state.gateway_port)

        # Update verify tab
        verify = self.query_one("#verify-content", Static)
        upstream = route.get("upstream", "unknown")
        verify.update(f"Route: {name}\nUpstream: {upstream}\n\nPress Ctrl+P to probe")

        # Update config tab
        config = self.query_one("#config-content", Markdown)
        domain = route.get("domain", state.system_domain)
        enabled = route.get("enabled", True)
        config_text = f"""
## Route Configuration

**Name:** `{name}`
**Upstream:** `{upstream}`
**Domain:** `{domain}`
**Enabled:** `{enabled}`

### Generated Caddy Snippet
```caddy
{name}.{domain} {{
    reverse_proxy http://{upstream}
}}
```
"""
        config.update(config_text)

        # Update integrity panel
        integrity = self.query_one(IntegrityPanel)
        integrity.update_integrity(state)
