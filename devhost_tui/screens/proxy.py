"""
Proxy screen — manage proxy modes, Caddy lifecycle, external proxy.

Covers: proxy status, upgrade, start/stop, port conflicts,
export/attach/detach, drift check, lockfile, transfer.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static

from ..cli_bridge import ProxyBridge

if TYPE_CHECKING:
    from ..app import DevhostDashboard


class ProxyScreen(Container):
    """Proxy management screen."""

    def compose(self) -> ComposeResult:
        yield Label("[b]⚙ Proxy Management[/b]", classes="section-title")
        with VerticalScroll(id="proxy-scroll"):
            # -- Status --
            yield Label("[b]Status[/b]", classes="subsection-title")
            yield Static("Loading...", id="proxy-status")

            # -- Mode --
            yield Label("[b]Current Mode[/b]", classes="subsection-title")
            yield Static("", id="proxy-mode-info")

            # -- Caddy Controls --
            yield Label("[b]Caddy Controls[/b] (system mode)", classes="subsection-title")
            with Horizontal(id="caddy-controls"):
                yield Button("Start Caddy", id="caddy-start", variant="success")
                yield Button("Stop Caddy", id="caddy-stop", variant="warning")
                yield Button("Reload", id="caddy-reload", variant="default")
                yield Button("Check Ports", id="check-ports", variant="default")
            yield Static("", id="caddy-status-detail")

            # -- External Proxy --
            yield Label("[b]External Proxy Integration[/b]", classes="subsection-title")
            yield Label("Driver:", classes="field-label")
            yield RadioSet(
                RadioButton("Caddy", id="driver-caddy", value=True),
                RadioButton("Nginx", id="driver-nginx"),
                RadioButton("Traefik", id="driver-traefik"),
                id="proxy-driver-select",
            )
            yield Label("Config Path:", classes="field-label")
            yield Input(placeholder="e.g., /etc/nginx/nginx.conf", id="proxy-config-path")
            with Horizontal(id="external-actions"):
                yield Button("Discover", id="proxy-discover", variant="default")
                yield Button("Export", id="proxy-export", variant="primary")
                yield Button("Attach", id="proxy-attach", variant="success")
                yield Button("Detach", id="proxy-detach", variant="warning")
            with Horizontal(id="external-actions-2"):
                yield Button("Validate", id="proxy-validate", variant="default")
                yield Button("Drift Check", id="proxy-drift", variant="default")
                yield Button("Accept Drift", id="proxy-drift-accept", variant="warning")
                yield Button("Sync Once", id="proxy-sync", variant="default")

            # -- Transfer --
            yield Label("[b]Transfer to External[/b]", classes="subsection-title")
            yield Static(
                "[dim]Transfer generates snippets and optionally attaches to your proxy config.[/dim]",
                id="transfer-desc",
            )
            with Horizontal(id="transfer-actions"):
                yield Button("Transfer", id="proxy-transfer", variant="primary")

            # -- Lockfile --
            yield Label("[b]Lockfile[/b]", classes="subsection-title")
            yield Label("Lock Path (optional):", classes="field-label")
            yield Input(placeholder="~/.devhost/devhost.lock.json", id="proxy-lock-path")
            with Horizontal(id="lock-actions"):
                yield Button("Write Lock", id="lock-write", variant="default")
                yield Button("Apply Lock", id="lock-apply", variant="primary")

            # -- Results --
            yield Label("[b]Results[/b]", classes="subsection-title")
            yield Static("", id="proxy-results")

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        self._load_status()

    @work(exclusive=True)
    async def _load_status(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        state = app.state
        session = app.session

        mode = session.proxy_mode
        domain = session.system_domain
        gateway_port = session.gateway_port

        mode_text = {
            "off": "[dim]Off — no proxy management[/dim]",
            "gateway": f"[green]Gateway[/green] — port {gateway_port}, domain: {domain}",
            "system": f"[cyan]System[/cyan] — Caddy on 80/443, domain: {domain}",
            "external": f"[yellow]External[/yellow] — driver: {session.external_driver}",
        }.get(mode, f"[dim]{mode}[/dim]")

        mode_info = self.query_one("#proxy-mode-info", Static)
        mode_info.update(mode_text)

        # Caddy status
        if mode == "system":
            caddy_info = await ProxyBridge.caddy_status(state)
            running = caddy_info.get("running", False)
            pid = caddy_info.get("pid")
            status_text = f"[green]Running[/green] (PID {pid})" if running else "[red]Stopped[/red]"
        else:
            status_text = "[dim]Not applicable (not in system mode)[/dim]"

        caddy_detail = self.query_one("#caddy-status-detail", Static)
        caddy_detail.update(status_text)

        # Overall
        status = self.query_one("#proxy-status", Static)
        status.update(f"Mode: {mode} • Domain: {domain} • Gateway: :{gateway_port}")

        # Pre-fill driver
        if mode == "external":
            self._set_driver(session.external_driver)
            if session.external_config_path:
                config_input = self.query_one("#proxy-config-path", Input)
                config_input.value = str(session.external_config_path)

    def _set_driver(self, driver: str) -> None:
        mapping = {"caddy": "driver-caddy", "nginx": "driver-nginx", "traefik": "driver-traefik"}
        target_id = mapping.get(driver, "driver-caddy")
        driver_select = self.query_one("#proxy-driver-select", RadioSet)
        for btn in driver_select.query(RadioButton):
            btn.value = btn.id == target_id

    def _selected_driver(self) -> str:
        driver_select = self.query_one("#proxy-driver-select", RadioSet)
        btn = driver_select.pressed_button
        if not btn:
            for candidate in driver_select.query(RadioButton):
                if candidate.value:
                    btn = candidate
                    break
        if not btn:
            return "caddy"
        return {"driver-caddy": "caddy", "driver-nginx": "nginx", "driver-traefik": "traefik"}.get(btn.id, "caddy")

    def _config_path(self) -> Path | None:
        value = self.query_one("#proxy-config-path", Input).value.strip()
        if value:
            return Path(value)
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        return app.state.external_config_path

    def _lock_path(self) -> Path | None:
        value = self.query_one("#proxy-lock-path", Input).value.strip()
        return Path(value) if value else None

    def _set_result(self, text: str) -> None:
        self.query_one("#proxy-results", Static).update(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        handlers = {
            "caddy-start": self._caddy_start,
            "caddy-stop": self._caddy_stop,
            "caddy-reload": self._caddy_reload,
            "check-ports": self._check_ports,
            "proxy-discover": self._discover,
            "proxy-export": self._export,
            "proxy-attach": self._attach,
            "proxy-detach": self._detach,
            "proxy-validate": self._validate,
            "proxy-drift": self._drift_check,
            "proxy-drift-accept": self._drift_accept,
            "proxy-sync": self._sync_once,
            "proxy-transfer": self._transfer,
            "lock-write": self._lock_write,
            "lock-apply": self._lock_apply,
        }
        handler = handlers.get(event.button.id)
        if handler:
            handler()

    @work(exclusive=True)
    async def _caddy_start(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        ok, msg = await ProxyBridge.start_caddy(app.state)
        app.notify(msg, severity="information" if ok else "error")
        self._set_result(msg)
        self.refresh_data()

    @work(exclusive=True)
    async def _caddy_stop(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        ok, msg = await ProxyBridge.stop_caddy(app.state)
        app.notify(msg, severity="information" if ok else "error")
        self._set_result(msg)
        self.refresh_data()

    @work(exclusive=True)
    async def _caddy_reload(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        ok, msg = await ProxyBridge.reload_caddy(app.state)
        app.notify(msg, severity="information" if ok else "error")
        self._set_result(msg)

    @work(exclusive=True)
    async def _check_ports(self) -> None:
        conflicts = await ProxyBridge.check_port_conflicts()
        if not conflicts:
            self._set_result("[green]No port conflicts detected.[/green]")
        else:
            lines = ["[yellow]Port conflicts:[/yellow]"]
            for c in conflicts:
                lines.append(f"  Port {c.get('port')}: {c.get('process', 'unknown')} (PID {c.get('pid', '?')})")
            self._set_result("\n".join(lines))

    @work(exclusive=True)
    async def _discover(self) -> None:
        driver = self._selected_driver()
        results = await ProxyBridge.discover_proxy_config(driver)
        if not results:
            self._set_result("No configs discovered. Enter a path manually.")
            return
        lines = ["Discovered configs:"]
        for drv, path in results:
            lines.append(f"  {drv}: {path}")
        self._set_result("\n".join(lines))
        if len(results) == 1:
            _, path = results[0]
            self.query_one("#proxy-config-path", Input).value = str(path)

    @work(exclusive=True)
    async def _export(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        driver = self._selected_driver()
        lock_path = self._lock_path()
        exported = await ProxyBridge.export_snippets(
            app.state, [driver], use_lock=lock_path is not None, lock_path=lock_path
        )
        snippet_path = exported.get(driver)
        if snippet_path:
            msg = f"Snippet exported: {snippet_path}"
            app.notify(msg, severity="information")
            self._set_result(msg)

    @work(exclusive=True)
    async def _attach(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        config_path = self._config_path()
        if not config_path:
            app.notify("Config path required.", severity="error")
            return
        driver = self._selected_driver()
        lock_path = self._lock_path()
        ok, msg = await ProxyBridge.attach_to_config(
            app.state, config_path, driver, use_lock=lock_path is not None, lock_path=lock_path
        )
        app.notify(msg, severity="information" if ok else "error")
        self._set_result(msg)

    @work(exclusive=True)
    async def _detach(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        config_path = self._config_path()
        if not config_path:
            app.notify("Config path required.", severity="error")
            return
        ok, msg = await ProxyBridge.detach_from_config(app.state, config_path)
        app.notify(msg, severity="information" if ok else "error")
        self._set_result(msg)

    @work(exclusive=True)
    async def _validate(self) -> None:
        config_path = self._config_path()
        if not config_path:
            self._set_result("Config path required for validation.")
            return
        driver = self._selected_driver()
        ok, msg = await ProxyBridge.validate_proxy_config(driver, config_path)
        self._set_result(f"Validation {'OK' if ok else 'FAILED'}: {msg}")

    @work(exclusive=True)
    async def _drift_check(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        driver = self._selected_driver()
        config_path = self._config_path()
        report = await ProxyBridge.check_proxy_drift(app.state, driver, config_path)
        if report.get("ok"):
            self._set_result("[green]No drift detected.[/green]")
        else:
            lines = ["[yellow]Drift detected:[/yellow]"]
            for issue in report.get("issues", []):
                code = issue.get("code", "unknown")
                message = issue.get("message", "")
                fix = issue.get("fix")
                line = f"  - {code}: {message}"
                if fix:
                    line += f" (fix: {fix})"
                lines.append(line)
            self._set_result("\n".join(lines))

    @work(exclusive=True)
    async def _drift_accept(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        driver = self._selected_driver()
        config_path = self._config_path()
        ok, msg = await ProxyBridge.accept_proxy_drift(app.state, driver, config_path)
        app.notify(msg, severity="information" if ok else "error")
        self._set_result(msg)

    @work(exclusive=True)
    async def _sync_once(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        driver = self._selected_driver()
        lock_path = self._lock_path()
        await ProxyBridge.sync_proxy(app.state, driver, use_lock=lock_path is not None, lock_path=lock_path)
        self._set_result("Sync complete.")

    @work(exclusive=True)
    async def _transfer(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        driver = self._selected_driver()
        config_path_val = self.query_one("#proxy-config-path", Input).value.strip() or None
        ok, msg = await ProxyBridge.transfer_to_external(
            app.state,
            driver,
            config_path=config_path_val,
        )
        app.notify(msg, severity="information" if ok else "error")
        self._set_result(msg)
        self.refresh_data()

    @work(exclusive=True)
    async def _lock_write(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        lock_path = self._lock_path()
        path = await ProxyBridge.write_lockfile(app.state, lock_path)
        msg = f"Lockfile written: {path}"
        app.notify(msg, severity="information")
        self._set_result(msg)

    @work(exclusive=True)
    async def _lock_apply(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        lock_path = self._lock_path()
        ok, msg = await ProxyBridge.apply_lockfile(app.state, lock_path)
        app.notify(msg, severity="information" if ok else "error")
        self._set_result(msg)
