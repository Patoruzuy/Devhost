"""
Settings screen — configuration, LAN access, OAuth, env sync.

Covers features that were previously only available via CLI:
- LAN / proxy expose
- OAuth URI helper
- Env file sync
- QR code generation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static

from ..cli_bridge import FeaturesBridge

if TYPE_CHECKING:
    from ..app import DevhostDashboard


class SettingsScreen(Container):
    """Settings and developer tools screen."""

    def compose(self) -> ComposeResult:
        yield Label("[b]⚙ Settings & Tools[/b]", classes="section-title")
        with VerticalScroll(id="settings-scroll"):
            # -- LAN Access --
            yield Label("[b]LAN Access[/b]", classes="subsection-title")
            yield Static("", id="lan-ip-info")
            with Horizontal(id="lan-actions"):
                yield Button("Detect LAN IP", id="detect-lan", variant="default")

            # -- OAuth Helper --
            yield Label("[b]OAuth URI Helper[/b]", classes="subsection-title")
            yield Static(
                "[dim]Generate OAuth callback URIs for your routes.[/dim]",
                id="oauth-desc",
            )
            yield Label("Route name:", classes="field-label")
            yield Input(placeholder="e.g., api", id="oauth-route")
            with Horizontal(id="oauth-actions"):
                yield Button("Generate URIs", id="oauth-generate", variant="primary")
            yield Static("", id="oauth-result")

            # -- Env Sync --
            yield Label("[b]Env File Sync[/b]", classes="subsection-title")
            yield Static(
                "[dim]Sync devhost URLs into your .env file.[/dim]",
                id="env-desc",
            )
            yield Label("Route (optional):", classes="field-label")
            yield Input(placeholder="Leave empty for all routes", id="env-route")
            yield Label("Env file:", classes="field-label")
            yield Input(placeholder=".env", value=".env", id="env-file")
            with Horizontal(id="env-actions"):
                yield Button("Dry Run", id="env-dry", variant="default")
                yield Button("Sync", id="env-sync", variant="primary")
            yield Static("", id="env-result")

            # -- QR Code --
            yield Label("[b]QR Code[/b]", classes="subsection-title")
            yield Static(
                "[dim]Generate QR codes for route URLs (mobile testing).[/dim]",
                id="qr-desc",
            )
            yield Label("Route:", classes="field-label")
            yield RadioSet(id="qr-route-select")
            with Horizontal(id="qr-actions"):
                yield Button("Show QR", id="qr-show", variant="primary")

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        self._load_routes_for_qr()
        self._detect_lan()

    def _load_routes_for_qr(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        qr_select = self.query_one("#qr-route-select", RadioSet)
        qr_select.remove_children()
        for i, name in enumerate(app.session.routes):
            qr_select.mount(RadioButton(name, id=f"qr-{name}", value=i == 0))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        handlers = {
            "detect-lan": self._detect_lan,
            "oauth-generate": self._generate_oauth,
            "env-dry": lambda: self._sync_env(dry_run=True),
            "env-sync": lambda: self._sync_env(dry_run=False),
            "qr-show": self._show_qr,
        }
        handler = handlers.get(event.button.id)
        if handler:
            handler()

    @work(exclusive=True)
    async def _detect_lan(self) -> None:
        ip = await FeaturesBridge.get_lan_ip()
        info = self.query_one("#lan-ip-info", Static)
        if ip:
            info.update(f"LAN IP: [green]{ip}[/green]")
        else:
            info.update("[yellow]Could not detect LAN IP.[/yellow]")

    @work(exclusive=True)
    async def _generate_oauth(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        route_name = self.query_one("#oauth-route", Input).value.strip()
        if not route_name:
            app.notify("Enter a route name.", severity="warning")
            return

        session = app.session
        domain = session.system_domain
        port = session.gateway_port if session.proxy_mode == "gateway" else None
        scheme = "https" if session.proxy_mode == "system" else "http"

        uris = await FeaturesBridge.get_oauth_uris(route_name, domain, port, scheme)
        result = self.query_one("#oauth-result", Static)
        if uris:
            lines = ["[b]OAuth Callback URIs:[/b]"]
            for uri in uris:
                lines.append(f"  {uri}")
            result.update("\n".join(lines))
        else:
            result.update("[dim]No URIs generated.[/dim]")

    @work(exclusive=True)
    async def _sync_env(self, dry_run: bool = False) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        route_name = self.query_one("#env-route", Input).value.strip() or None
        env_file = self.query_one("#env-file", Input).value.strip() or ".env"

        ok = await FeaturesBridge.sync_env_file(route_name, env_file, dry_run)
        result = self.query_one("#env-result", Static)
        label = "Dry run" if dry_run else "Sync"
        if ok:
            result.update(f"[green]{label} complete.[/green]")
            app.notify(f"{label} complete.", severity="information")
        else:
            result.update(f"[red]{label} failed.[/red]")
            app.notify(f"{label} failed.", severity="error")

    def _show_qr(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        qr_select = self.query_one("#qr-route-select", RadioSet)
        btn = qr_select.pressed_button
        if not btn or not btn.id:
            app.notify("Select a route.", severity="warning")
            return
        route_name = btn.id.removeprefix("qr-")
        route = app.session.get_route(route_name)
        if not route:
            app.notify("Route not found.", severity="error")
            return

        from devhost_cli.validation import get_dev_scheme

        domain = route.get("domain", app.session.system_domain)
        upstream = route.get("upstream", "")
        if app.session.proxy_mode == "gateway":
            url = f"http://{route_name}.{domain}:{app.session.gateway_port}"
        else:
            scheme = get_dev_scheme(upstream)
            url = f"{scheme}://{route_name}.{domain}"

        from ..modals import QRCodeModal

        app.push_screen(QRCodeModal(route_name, url))
