"""
Tunnels screen — manage tunnel providers and active tunnels.

Shows available providers, active tunnels, and start/stop controls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, DataTable, Label, RadioButton, RadioSet, Static

from ..cli_bridge import TunnelBridge

if TYPE_CHECKING:
    from ..app import DevhostDashboard


class TunnelsScreen(Container):
    """Tunnel management screen."""

    def compose(self) -> ComposeResult:
        yield Label("[b]🔗 Tunnels[/b]", classes="section-title")
        yield Static(
            "[dim]Expose local routes to the internet via tunnel providers.[/dim]",
            id="tunnel-desc",
        )
        yield Label("Available Providers:", classes="field-label")
        yield Static("Scanning...", id="providers-list")
        yield Label("Active Tunnels:", classes="field-label")
        yield DataTable(id="tunnels-table")
        yield Label("Select a route to tunnel:", classes="field-label")
        yield RadioSet(id="tunnel-route-select")
        yield Label("Provider:", classes="field-label")
        yield RadioSet(id="tunnel-provider-select")
        with Horizontal(id="tunnel-actions"):
            yield Button("Start Tunnel", id="tunnel-start", variant="success")
            yield Button("Stop Tunnel", id="tunnel-stop", variant="warning")
            yield Button("Stop All", id="tunnel-stop-all", variant="error")
            yield Button("Refresh", id="tunnel-refresh", variant="default")

    def on_mount(self) -> None:
        table = self.query_one("#tunnels-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_column("Route", key="route", width=18)
        table.add_column("Provider", key="provider", width=14)
        table.add_column("Public URL", key="url", width=40)
        table.add_column("PID", key="pid", width=8)
        self.refresh_data()

    def refresh_data(self) -> None:
        self._load_providers()
        self._load_tunnels()
        self._load_routes()

    @work(exclusive=True)
    async def _load_providers(self) -> None:
        providers = await TunnelBridge.available_providers()
        providers_widget = self.query_one("#providers-list", Static)
        if providers:
            text = ", ".join(f"[green]✓[/green] {p}" for p in providers)
        else:
            text = "[yellow]No tunnel providers found. Install cloudflared, ngrok, or localtunnel.[/yellow]"
        providers_widget.update(text)

        # Populate provider radio buttons
        provider_select = self.query_one("#tunnel-provider-select", RadioSet)
        provider_select.remove_children()
        for i, p in enumerate(providers):
            provider_select.mount(RadioButton(p, id=f"provider-{p}", value=i == 0))

    @work(exclusive=True)
    async def _load_tunnels(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        tunnels = await TunnelBridge.status(app.state)
        table = self.query_one("#tunnels-table", DataTable)
        table.clear()
        if not tunnels:
            table.add_row("No active tunnels", "", "", "", key="empty")
            return
        for t in tunnels:
            table.add_row(
                t.route_name,
                t.provider,
                t.public_url or "[dim]connecting...[/dim]",
                str(t.pid or "-"),
                key=t.route_name,
            )

    def _load_routes(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        route_select = self.query_one("#tunnel-route-select", RadioSet)
        route_select.remove_children()
        routes = app.session.routes
        for i, name in enumerate(routes):
            route_select.mount(RadioButton(name, id=f"route-{name}", value=i == 0))

    def _selected_route(self) -> str | None:
        route_select = self.query_one("#tunnel-route-select", RadioSet)
        btn = route_select.pressed_button
        if btn and btn.id:
            return btn.id.removeprefix("route-")
        return None

    def _selected_provider(self) -> str | None:
        provider_select = self.query_one("#tunnel-provider-select", RadioSet)
        btn = provider_select.pressed_button
        if btn and btn.id:
            return btn.id.removeprefix("provider-")
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "tunnel-start":
            self._start_tunnel()
        elif event.button.id == "tunnel-stop":
            self._stop_tunnel()
        elif event.button.id == "tunnel-stop-all":
            self._stop_all_tunnels()
        elif event.button.id == "tunnel-refresh":
            self.refresh_data()

    @work(exclusive=True)
    async def _start_tunnel(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        route = self._selected_route()
        provider = self._selected_provider()
        if not route:
            app.notify("Select a route to tunnel.", severity="warning")
            return
        app.notify(f"Starting tunnel for {route}...", severity="information")
        ok, msg = await TunnelBridge.start(app.state, route, provider)
        app.notify(msg, severity="information" if ok else "error")
        self.refresh_data()

    @work(exclusive=True)
    async def _stop_tunnel(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        route = self._selected_route()
        if not route:
            app.notify("Select a tunnel to stop.", severity="warning")
            return
        ok, msg = await TunnelBridge.stop(app.state, route)
        app.notify(msg, severity="information" if ok else "error")
        self.refresh_data()

    @work(exclusive=True)
    async def _stop_all_tunnels(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        ok, msg = await TunnelBridge.stop(app.state, None)
        app.notify(msg, severity="information" if ok else "error")
        self.refresh_data()
