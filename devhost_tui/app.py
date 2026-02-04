"""
Devhost TUI - Main Application

Interactive terminal dashboard for managing local development routing.
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import (
    DataTable,
    Footer,
    Header,
)

from devhost_cli.state import StateConfig

from .widgets import DetailsPane, Sidebar, StatusGrid


class DevhostDashboard(App):
    """The main Devhost TUI application."""

    TITLE = "Devhost Dashboard"
    SUB_TITLE = "Local Development Router"

    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 2;
        grid-columns: 1fr 3fr 1fr;
        grid-rows: 1fr 1fr;
    }

    #sidebar {
        column-span: 1;
        row-span: 2;
        background: $surface;
        border-right: solid $primary;
        padding: 1;
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
        Binding("ctrl+x", "emergency_reset", "Emergency Reset"),
        Binding("a", "add_route", "Add Route"),
        Binding("d", "delete_route", "Delete Route"),
        Binding("o", "open_url", "Open URL"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.state = StateConfig()
        self.selected_route: str | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Sidebar(id="sidebar")
        yield StatusGrid(id="main-grid")
        yield DetailsPane(id="details")
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        self.refresh_data()

    def refresh_data(self) -> None:
        """Refresh all data from state."""
        self.state.reload()

        # Update status grid
        grid = self.query_one(StatusGrid)
        grid.update_routes(
            self.state.routes,
            self.state.proxy_mode,
            self.state.system_domain,
            self.state.gateway_port,
        )

        # Update sidebar
        sidebar = self.query_one(Sidebar)
        sidebar.update_state(self.state)

        # Update details if a route is selected
        if self.selected_route:
            details = self.query_one(DetailsPane)
            route = self.state.get_route(self.selected_route)
            if route:
                details.show_route(self.selected_route, route, self.state)

    def action_refresh(self) -> None:
        """Refresh data."""
        self.refresh_data()
        self.notify("Data refreshed", severity="information")

    def action_integrity_check(self) -> None:
        """Run integrity check."""
        results = self.state.check_all_integrity()
        issues = [path for path, (ok, _) in results.items() if not ok]
        if issues:
            self.notify(f"Integrity issues found: {len(issues)} files", severity="warning")
        else:
            self.notify("All files OK", severity="information")

    def action_probe_routes(self) -> None:
        """Probe all routes."""
        self.notify("Probing routes...", severity="information")
        # TODO: Implement async probing

    def action_emergency_reset(self) -> None:
        """Emergency reset - kill owned processes only."""
        from .modals import ConfirmResetModal

        self.push_screen(ConfirmResetModal())

    def action_add_route(self) -> None:
        """Show add route wizard."""
        from .modals import AddRouteWizard

        self.push_screen(AddRouteWizard())

    def action_delete_route(self) -> None:
        """Delete selected route."""
        if self.selected_route:
            self.state.remove_route(self.selected_route)
            if self.state.proxy_mode == "system":
                from devhost_cli.caddy_lifecycle import write_system_caddyfile

                write_system_caddyfile(self.state)
            elif self.state.proxy_mode == "external":
                from devhost_cli.proxy import export_snippets

                export_snippets(self.state, [self.state.external_driver])
            self.notify(f"Removed route: {self.selected_route}", severity="information")
            self.selected_route = None
            self.refresh_data()

    def action_open_url(self) -> None:
        """Open selected route URL in browser."""
        if self.selected_route:
            import webbrowser

            route = self.state.get_route(self.selected_route)
            if route:
                domain = route.get("domain", self.state.system_domain)
                mode = self.state.proxy_mode
                if mode == "gateway":
                    url = f"http://{self.selected_route}.{domain}:{self.state.gateway_port}"
                elif mode == "system":
                    url = f"http://{self.selected_route}.{domain}"
                else:
                    url = f"http://{self.selected_route}.{domain}"
                webbrowser.open(url)
                self.notify(f"Opened: {url}", severity="information")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle route selection in the grid."""
        # Get route name from the selected row
        row_key = event.row_key
        if row_key:
            # The row key is the route name
            self.selected_route = str(row_key.value)
            details = self.query_one(DetailsPane)
            route = self.state.get_route(self.selected_route)
            if route:
                details.show_route(self.selected_route, route, self.state)


def run_dashboard():
    """Run the Devhost dashboard."""
    app = DevhostDashboard()
    app.run()


if __name__ == "__main__":
    run_dashboard()
