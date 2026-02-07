"""
Devhost TUI - Modal Dialogs

Contains modal screens for:
- AddRouteWizard: Multi-step wizard to add a new route
- ConfirmResetModal: Emergency reset confirmation
- ExternalProxyModal: Attach/detach external proxy configs
"""

import ipaddress
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Markdown, RadioButton, RadioSet, Static

from devhost_cli.state import StateConfig, parse_listen


class ExternalProxyModal(ModalScreen[bool]):
    """Attach/detach devhost snippets to an external proxy config."""

    CSS = """
    ExternalProxyModal {
        align: center middle;
    }

    #external-dialog {
        width: 85%;
        max-width: 90;
        min-width: 50;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 2;
    }

    #external-dialog Label {
        width: 100%;
        margin-bottom: 1;
    }

    #discover-results {
        height: auto;
        max-height: 8;
        margin: 1 0;
        padding: 1;
        background: $surface-darken-1;
        border: round $primary-darken-2;
    }

    #external-buttons {
        margin-top: 2;
        width: 100%;
        align: right middle;
    }

    #external-buttons Button {
        margin: 0 1;
    }

    #external-buttons-secondary,
    #external-buttons-tertiary {
        margin-top: 1;
        width: 100%;
        align: right middle;
    }

    #external-buttons-secondary Button,
    #external-buttons-tertiary Button {
        margin: 0 1;
    }
    """

    def __init__(self):
        super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical(id="external-dialog"):
            yield Label("[b]External Proxy Attach/Detach[/b]")
            yield Label("[yellow]Edits user-owned proxy configs. Backups are created before changes.[/yellow]")
            yield Label("Select proxy driver:")
            yield RadioSet(
                RadioButton("Caddy", id="driver-caddy"),
                RadioButton("Nginx", id="driver-nginx"),
                RadioButton("Traefik", id="driver-traefik"),
                id="driver-select",
            )
            yield Label("Config Path (optional):")
            yield Input(placeholder="e.g., /etc/nginx/nginx.conf", id="config-path")
            yield Label("Lockfile Path (optional):")
            yield Input(placeholder="e.g., ~/.devhost/devhost.lock.json", id="lock-path")
            yield Static("Discover a config file to prefill the path.", id="discover-results")
            yield Static("", id="action-results")
            yield Static("Reload hint will appear here.", id="reload-hint")
            with Horizontal(id="external-buttons"):
                yield Button("Discover", variant="default", id="discover")
                yield Button("Export Snippet", variant="primary", id="export")
                yield Button("Attach", variant="success", id="attach")
                yield Button("Detach", variant="warning", id="detach")
            with Horizontal(id="external-buttons-secondary"):
                yield Button("Drift Check", variant="default", id="drift")
                yield Button("Accept Drift", variant="warning", id="drift-accept")
                yield Button("Validate", variant="default", id="validate")
                yield Button("Show Reload Hint", variant="default", id="reload")
            with Horizontal(id="external-buttons-tertiary"):
                yield Button("Write Lock", variant="default", id="lock-write")
                yield Button("Apply Lock", variant="primary", id="lock-apply")
                yield Button("Sync Once", variant="default", id="sync-once")
                yield Button("Close", variant="default", id="close")

    def on_mount(self) -> None:
        state = getattr(self.app, "state", None) or StateConfig()
        driver = getattr(state, "external_driver", "caddy")
        self._set_selected_driver(driver)
        config_input = self.query_one("#config-path", Input)
        if state.external_config_path:
            config_input.value = str(state.external_config_path)
        self._update_discover_text("Discover a config file to prefill the path.")

    def _set_selected_driver(self, driver: str) -> None:
        driver_select = self.query_one("#driver-select", RadioSet)
        mapping = {
            "caddy": "driver-caddy",
            "nginx": "driver-nginx",
            "traefik": "driver-traefik",
        }
        target = mapping.get(driver, "driver-caddy")
        for button in driver_select.query(RadioButton):
            button.value = button.id == target

    def _selected_driver(self) -> str:
        driver_select = self.query_one("#driver-select", RadioSet)
        button = driver_select.pressed_button
        if not button:
            for candidate in driver_select.query(RadioButton):
                if candidate.value:
                    button = candidate
                    break
        if not button:
            return "caddy"
        button_id = button.id
        return {
            "driver-caddy": "caddy",
            "driver-nginx": "nginx",
            "driver-traefik": "traefik",
        }.get(button_id, "caddy")

    def _get_config_path(self) -> Path | None:
        config_input = self.query_one("#config-path", Input)
        value = config_input.value.strip()
        if value:
            return Path(value)
        state = getattr(self.app, "state", None) or StateConfig()
        return state.external_config_path

    def _get_lock_path(self) -> Path | None:
        lock_input = self.query_one("#lock-path", Input)
        value = lock_input.value.strip()
        return Path(value) if value else None

    def _update_discover_text(self, message: str) -> None:
        discover = self.query_one("#discover-results", Static)
        discover.update(message)

    def _update_action_text(self, message: str) -> None:
        results = self.query_one("#action-results", Static)
        results.update(message)

    def _update_reload_hint(self, message: str) -> None:
        hint = self.query_one("#reload-hint", Static)
        hint.update(message)

    def _reload_hint(self, driver: str, config_path: Path | None) -> str:
        path = str(config_path) if config_path else "<path>"
        if driver == "caddy":
            return f"Reload hint: caddy reload --config {path}"
        if driver == "nginx":
            return "Reload hint: nginx -s reload (or systemctl reload nginx)"
        if driver == "traefik":
            return "Reload hint: restart Traefik service/container to apply file changes"
        return "Reload hint: reload your proxy to apply changes"

    def _guard_pending_changes(self) -> bool:
        session = getattr(self.app, "session", None)
        if session and session.has_changes():
            self.app.notify("Apply draft changes before modifying external proxy.", severity="warning")
            return False
        return True

    def _refresh_state(self) -> None:
        if hasattr(self.app, "refresh_data"):
            self.app.refresh_data()
        if hasattr(self.app, "action_integrity_check"):
            self.app.action_integrity_check()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from devhost_cli.proxy import (
            accept_proxy_drift,
            apply_lockfile,
            attach_to_config,
            check_proxy_drift,
            detach_from_config,
            discover_proxy_config,
            export_snippets,
            sync_proxy,
            validate_proxy_config,
            write_lockfile,
        )

        if event.button.id == "close":
            self.dismiss(False)
            return

        driver = self._selected_driver()
        lock_path = self._get_lock_path()
        use_lock = lock_path is not None
        if event.button.id in {"export", "attach", "sync-once", "lock-apply"}:
            if use_lock and lock_path and not lock_path.exists():
                self._update_action_text(f"Lockfile not found: {lock_path}")
                return

        if event.button.id == "discover":
            results = discover_proxy_config(driver)
            if not results:
                self._update_discover_text("No configs discovered. Enter a path manually.")
                return
            lines = ["Discovered configs:"]
            for drv, path in results:
                lines.append(f"  {drv}: {path}")
            self._update_discover_text("\n".join(lines))
            if len(results) == 1:
                _, path = results[0]
                config_input = self.query_one("#config-path", Input)
                config_input.value = str(path)
            return

        if event.button.id == "reload":
            config_path = self._get_config_path()
            self.app.push_screen(ConfirmReloadModal(self._reload_hint(driver, config_path)))
            return

        if event.button.id == "export":
            state = getattr(self.app, "state", None) or StateConfig()
            exported = export_snippets(state, [driver], use_lock=use_lock, lock_path=lock_path)
            snippet_path = exported.get(driver)
            if snippet_path:
                self.app.notify(f"Snippet exported: {snippet_path}", severity="information")
                self._update_action_text(f"Exported snippet: {snippet_path}")
            self._refresh_state()
            return

        if event.button.id == "attach":
            if not self._guard_pending_changes():
                return
            config_path = self._get_config_path()
            if not config_path:
                self.app.notify("Config path required for attach.", severity="error")
                return
            state = getattr(self.app, "state", None) or StateConfig()
            success, msg = attach_to_config(
                state, config_path, driver, validate=True, use_lock=use_lock, lock_path=lock_path
            )
            self.app.notify(msg, severity="information" if success else "error")
            self._update_action_text(msg)
            if success:
                self._refresh_state()
            return

        if event.button.id == "detach":
            if not self._guard_pending_changes():
                return
            config_path = self._get_config_path()
            if not config_path:
                self.app.notify("Config path required for detach.", severity="error")
                return
            state = getattr(self.app, "state", None) or StateConfig()
            success, msg = detach_from_config(state, config_path)
            self.app.notify(msg, severity="information" if success else "error")
            self._update_action_text(msg)
            if success:
                self._refresh_state()
            return

        if event.button.id == "drift":
            state = getattr(self.app, "state", None) or StateConfig()
            config_path = self._get_config_path()
            report = check_proxy_drift(state, driver, config_path, validate=False)
            if report.get("ok"):
                msg = "No drift detected."
            else:
                lines = ["Drift detected:"]
                for issue in report.get("issues", []):
                    code = issue.get("code", "unknown")
                    message = issue.get("message", "")
                    fix = issue.get("fix")
                    line = f"- {code}: {message}"
                    if fix:
                        line += f" (fix: {fix})"
                    lines.append(line)
                msg = "\n".join(lines)
            self._update_action_text(msg)
            return

        if event.button.id == "drift-accept":
            state = getattr(self.app, "state", None) or StateConfig()
            config_path = self._get_config_path()
            success, msg = accept_proxy_drift(state, driver, config_path)
            self.app.notify(msg, severity="information" if success else "error")
            self._update_action_text(msg)
            if success:
                self._refresh_state()
            return

        if event.button.id == "validate":
            config_path = self._get_config_path()
            if not config_path:
                self._update_action_text("Config path required for validation.")
                return
            ok, msg = validate_proxy_config(driver, config_path)
            self._update_action_text(f"Validation {'OK' if ok else 'FAILED'}: {msg}")
            return

        if event.button.id == "lock-write":
            state = getattr(self.app, "state", None) or StateConfig()
            path = write_lockfile(state, lock_path)
            msg = f"Lockfile written: {path}"
            self.app.notify(msg, severity="information")
            self._update_action_text(msg)
            return

        if event.button.id == "lock-apply":
            if not self._guard_pending_changes():
                return
            state = getattr(self.app, "state", None) or StateConfig()
            success, msg = apply_lockfile(state, lock_path, update_config=True)
            self.app.notify(msg, severity="information" if success else "error")
            self._update_action_text(msg)
            if success:
                self._refresh_state()
            return

        if event.button.id == "sync-once":
            state = getattr(self.app, "state", None) or StateConfig()
            sync_proxy(state, driver, watch=False, use_lock=use_lock, lock_path=lock_path)
            self._update_action_text("Sync complete.")
            self._refresh_state()
            return


class DiagnosticsPreviewModal(ModalScreen[bool]):
    """Preview diagnostic bundle contents."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
    ]

    CSS = """
    DiagnosticsPreviewModal {
        align: center middle;
    }

    #diagnostics-preview {
        width: 90%;
        max-width: 100;
        min-width: 60;
        height: auto;
        max-height: 30;
        border: thick $primary;
        background: $surface;
        padding: 2;
    }

    #diagnostics-preview Static {
        width: 100%;
    }
    """

    def __init__(self, preview: dict):
        super().__init__()
        self._preview = preview

    def compose(self) -> ComposeResult:
        with Vertical(id="diagnostics-preview"):
            yield Label("[b]Diagnostics Preview[/b]")
            yield Static(self._format_preview(), id="diagnostics-preview-content")
            yield Button("Close", id="diagnostics-preview-close")

    def _format_preview(self) -> str:
        included = self._preview.get("included", [])
        included_sorted = self._preview.get("included_sorted", included)
        missing = self._preview.get("missing", [])
        total_size = self._preview.get("total_size_human", "0B")
        size_limit = self._preview.get("size_limit_human")
        over_limit = self._preview.get("over_limit", False)
        redacted_count = self._preview.get("redacted_count", 0)
        redaction_cfg = self._preview.get("redaction_config", {})
        redaction_source = redaction_cfg.get("source")
        redaction_errors = redaction_cfg.get("errors", [])
        top_n = 20
        lines = [
            f"Files: {len(included)}",
            f"Total size: {total_size}",
            f"Redacted: {redacted_count}",
        ]
        if size_limit:
            lines.append(f"Size limit: {size_limit}")
        if over_limit:
            lines.append("Status: over limit")
        if redaction_source:
            lines.append(f"Redaction config: {redaction_source}")
        if redaction_errors:
            lines.append(f"Redaction errors: {len(redaction_errors)}")
        if missing:
            lines.append(f"Missing: {len(missing)}")
        lines.append("")
        lines.append("")
        lines.append(f"Top {top_n} largest files:")
        for item in included_sorted[:top_n]:
            suffix = " (redacted)" if item.get("redact") else ""
            size = item.get("size", 0)
            lines.append(f"- {item.get('path')} ({size}B){suffix}")
        if len(included) > top_n:
            lines.append(f"... and {len(included) - top_n} more")
        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "diagnostics-preview-close":
            self.dismiss()


class QRCodeModal(ModalScreen[None]):
    """Shows QR code for a route with domain details."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
    ]

    CSS = """
    QRCodeModal {
        align: center middle;
    }

    QRCodeModal > Container {
        width: 85%;
        max-width: 100;
        min-width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 2;
    }

    QRCodeModal Static {
        padding: 1;
    }
    """

    def __init__(self, route_name: str, url: str):
        super().__init__()
        self.route_name = route_name
        self.url = url

    def compose(self) -> ComposeResult:
        qr_text = None
        lan_ip = None
        error_msg = None

        try:
            from devhost_cli.features import generate_qr_code, get_lan_ip

            lan_ip = get_lan_ip()
            qr_text = generate_qr_code(self.url, quiet=True)
        except ImportError:
            error_msg = "[yellow]QR code unavailable. Install with: pip install 'devhost[qr]'[/yellow]"
        except Exception as e:
            error_msg = f"[red]QR generation error: {str(e)}[/red]"

        mobile_url = self.url.replace("localhost", lan_ip) if lan_ip else self.url

        with Container():
            yield Static(f"[bold cyan]Route:[/] {self.route_name}", id="route-name")
            yield Static(f"[bold]URL:[/] {self.url}")
            if lan_ip:
                yield Static(f"[bold]Mobile:[/] {mobile_url}")
            yield Static("")  # spacer
            if error_msg:
                yield Static(error_msg)
            elif qr_text:
                yield Static(qr_text, id="qr-code")
            else:
                yield Static("[yellow]QR code generation returned empty result[/yellow]")
            yield Static("")
            yield Button("Close", variant="primary", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


class IntegrityDiffModal(ModalScreen[bool]):
    """Show unified diff for integrity drift."""

    CSS = """
    IntegrityDiffModal {
        align: center middle;
    }

    #integrity-diff {
        width: 90%;
        max-width: 100;
        min-width: 60;
        height: auto;
        max-height: 30;
        border: thick $primary;
        background: $surface;
        padding: 2;
    }
    """

    def __init__(self, diff_text: str):
        super().__init__()
        self._diff_text = diff_text

    def compose(self) -> ComposeResult:
        with Vertical(id="integrity-diff"):
            yield Label("[b]Integrity Diff[/b]")
            yield Static(self._diff_text, id="integrity-diff-content")
            yield Button("Close", id="integrity-diff-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "integrity-diff-close":
            self.dismiss(True)


class ConfirmRestoreModal(ModalScreen[bool]):
    """Confirm restoring a backup over a drifted file."""

    CSS = """
    ConfirmRestoreModal {
        align: center middle;
    }

    #restore-dialog {
        width: 70;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 2;
    }
    """

    def __init__(self, target: Path, backup: Path):
        super().__init__()
        self._target = target
        self._backup = backup

    def compose(self) -> ComposeResult:
        with Vertical(id="restore-dialog"):
            yield Label("[b]Restore Backup[/b]")
            yield Label(f"Target: {self._target}")
            yield Label(f"Backup: {self._backup}")
            yield Label("This will overwrite the current file.")
            with Horizontal():
                yield Button("Cancel", id="restore-cancel")
                yield Button("Restore", id="restore-confirm", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "restore-confirm":
            if hasattr(self.app, "perform_restore"):
                self.app.perform_restore(self._target, self._backup)
            self.dismiss(True)
        elif event.button.id == "restore-cancel":
            self.dismiss(False)


class ConfirmReloadModal(ModalScreen[bool]):
    """Confirm showing reload instructions."""

    CSS = """
    ConfirmReloadModal {
        align: center middle;
    }

    #reload-dialog {
        width: 70;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 2;
    }
    """

    def __init__(self, hint: str):
        super().__init__()
        self._hint = hint

    def compose(self) -> ComposeResult:
        with Vertical(id="reload-dialog"):
            yield Label("[b]Reload Proxy[/b]")
            yield Label("This will show the reload command. It will not run automatically.")
            yield Label(self._hint)
            with Horizontal():
                yield Button("Close", id="reload-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "reload-close":
            self.dismiss(True)


class ConfirmProxyExposeModal(ModalScreen[bool]):
    """Confirm exposing Devhost on the LAN."""

    CSS = """
    ConfirmProxyExposeModal {
        align: center middle;
    }

    #expose-dialog {
        width: 70;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 2;
    }

    #expose-dialog Label {
        width: 100%;
        margin-bottom: 1;
    }

    #expose-buttons {
        margin-top: 2;
        width: 100%;
        align: right middle;
    }

    #expose-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, target: str, parent: ModalScreen | None = None):
        super().__init__()
        self._target = target
        self._parent = parent

    def compose(self) -> ComposeResult:
        with Vertical(id="expose-dialog"):
            yield Label("[b]Confirm LAN Exposure[/b]")
            yield Label(f"Target bind: {self._target}")
            yield Label("[yellow]This makes Devhost reachable from other devices on your network.[/yellow]")
            yield Label("Rollback: devhost proxy expose --local")
            with Horizontal(id="expose-buttons"):
                yield Button("Cancel", variant="default", id="expose-cancel")
                yield Button("Expose", variant="warning", id="expose-confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "expose-confirm":
            if hasattr(self.app, "perform_proxy_expose"):
                self.app.perform_proxy_expose(self._target)
            if self._parent:
                self._parent.dismiss(True)
            self.dismiss(True)
        elif event.button.id == "expose-cancel":
            self.dismiss(False)


class ProxyExposeModal(ModalScreen[bool]):
    """Configure gateway/system bind address for LAN access."""

    CSS = """
    ProxyExposeModal {
        align: center middle;
    }

    #proxy-expose-dialog {
        width: 80;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 2;
    }

    #proxy-expose-dialog Label {
        width: 100%;
        margin-bottom: 1;
    }

    #proxy-expose-buttons {
        margin-top: 2;
        width: 100%;
        align: right middle;
    }

    #proxy-expose-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self):
        super().__init__()
        self._gateway_listen = "127.0.0.1:7777"
        self._system_listen_http = "127.0.0.1:80"

    def compose(self) -> ComposeResult:
        with Vertical(id="proxy-expose-dialog"):
            yield Label("[b]LAN Access[/b]")
            yield Label("[yellow]Exposing Devhost to the LAN is opt-in and requires confirmation.[/yellow]")
            yield Static("", id="current-bindings")
            yield Label("Bind target:")
            yield RadioSet(
                RadioButton("Localhost only (127.0.0.1)", id="bind-local"),
                RadioButton("LAN (0.0.0.0)", id="bind-lan"),
                RadioButton("Specific IPv4 address", id="bind-iface"),
                id="bind-select",
            )
            yield Input(placeholder="e.g., 192.168.1.10", id="bind-ip")
            yield Label("Rollback: devhost proxy expose --local")
            with Horizontal(id="proxy-expose-buttons"):
                yield Button("Cancel", variant="default", id="proxy-expose-cancel")
                yield Button("Apply", variant="primary", id="proxy-expose-apply")

    def on_mount(self) -> None:
        state = getattr(self.app, "state", None) or StateConfig()
        self._gateway_listen = state.gateway_listen
        self._system_listen_http = state.raw.get("proxy", {}).get("system", {}).get("listen_http", "127.0.0.1:80")
        current = self.query_one("#current-bindings", Static)
        current.update(
            f"Current gateway listen: {self._gateway_listen}\nCurrent system listen: {self._system_listen_http}"
        )

        gateway_host, _ = parse_listen(self._gateway_listen, "127.0.0.1", 7777)
        bind_select = self.query_one("#bind-select", RadioSet)
        bind_ip = self.query_one("#bind-ip", Input)

        if gateway_host == "0.0.0.0":
            bind_select.query_one("#bind-lan", RadioButton).value = True
        elif gateway_host == "127.0.0.1":
            bind_select.query_one("#bind-local", RadioButton).value = True
        else:
            bind_select.query_one("#bind-iface", RadioButton).value = True
            bind_ip.value = gateway_host or ""

    def _guard_pending_changes(self) -> bool:
        session = getattr(self.app, "session", None)
        if session and session.has_changes():
            self.app.notify("Apply draft changes before updating proxy bindings.", severity="warning")
            return False
        return True

    def _selected_target(self) -> tuple[str | None, str | None]:
        bind_select = self.query_one("#bind-select", RadioSet)
        button = bind_select.pressed_button
        if not button:
            for candidate in bind_select.query(RadioButton):
                if candidate.value:
                    button = candidate
                    break
        if not button:
            return None, "Select a bind target."

        if button.id == "bind-local":
            return "127.0.0.1", None
        if button.id == "bind-lan":
            return "0.0.0.0", None
        if button.id == "bind-iface":
            bind_ip = self.query_one("#bind-ip", Input)
            value = bind_ip.value.strip()
            if not value:
                return None, "Interface IP required."
            try:
                addr = ipaddress.ip_address(value)
            except ValueError:
                return None, "Invalid IP address."
            if isinstance(addr, ipaddress.IPv6Address):
                return None, "IPv6 binding not supported. Use an IPv4 address."
            return value, None
        return None, "Select a bind target."

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "proxy-expose-cancel":
            self.dismiss(False)
            return

        if event.button.id == "proxy-expose-apply":
            if not self._guard_pending_changes():
                return
            target, error = self._selected_target()
            if error:
                self.app.notify(error, severity="error")
                return
            if not target:
                self.app.notify("No bind target selected.", severity="error")
                return
            if target != "127.0.0.1":
                self.app.push_screen(ConfirmProxyExposeModal(target, parent=self))
                return
            if hasattr(self.app, "perform_proxy_expose"):
                self.app.perform_proxy_expose(target)
            self.dismiss(True)


class ConfirmResetModal(ModalScreen[bool]):
    """Modal to confirm emergency reset."""

    CSS = """
    ConfirmResetModal {
        align: center middle;
    }

    #reset-dialog {
        width: 60;
        height: auto;
        border: thick $error;
        background: $surface;
        padding: 2;
    }

    #reset-dialog Label {
        width: 100%;
        margin-bottom: 1;
    }

    #reset-buttons {
        margin-top: 2;
        width: 100%;
        align: center middle;
    }

    #reset-buttons Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="reset-dialog"):
            yield Label("[b]⚠️ Emergency Reset[/b]")
            yield Label("This will:")
            yield Label("  • Kill all Devhost-owned processes")
            yield Label("  • Revert to gateway mode")
            yield Label("  • Clear runtime state")
            yield Label("")
            yield Label("[yellow]External proxies will NOT be touched.[/yellow]")
            yield Label("")
            yield Label("Are you sure you want to continue?")
            with Horizontal(id="reset-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Reset", variant="error", id="confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self._perform_reset()
            self.dismiss(True)
        else:
            self.dismiss(False)

    def _perform_reset(self) -> None:
        """Perform the emergency reset."""
        from devhost_cli.caddy_lifecycle import stop_caddy

        state = getattr(self.app, "session", None) or StateConfig()

        # Stop Caddy if running in system mode
        if state.proxy_mode == "system":
            stop_caddy(state, force=True)

        # Reset to gateway mode
        state.proxy_mode = "gateway"

        self.app.notify("Emergency reset complete", severity="warning")


class HelpModal(ModalScreen[None]):
    """Display keyboard shortcuts and commands help."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    CSS = """
    HelpModal {
        align: center middle;
    }

    #help-dialog {
        width: 90%;
        max-width: 120;
        min-width: 80;
        height: 85%;
        border: thick $primary;
        background: $surface;
        padding: 2;
    }

    #help-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
        padding: 1;
        background: $primary-darken-1;
    }

    #help-content {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }

    #help-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
        padding: 1;
    }

    #help-buttons Button {
        min-width: 12;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield Static("📖 Devhost Dashboard - Keyboard Shortcuts", id="help-title")
            yield Markdown(
                """
## Navigation
- `↑` `↓` - Navigate routes in table
- `Tab` - Cycle through panes and tabs
- `/` - Open command palette
- `Enter` - Select route / Execute command

## Route Actions
- `A` - Add new route (opens wizard)
- `D` - Delete selected route
- `O` - Open route URL in browser
- `Y` - Copy full URL to clipboard
- `H` - Copy host header to clipboard
- `U` - Copy upstream target to clipboard

## System Operations
- `Ctrl+R` - Refresh all data
- `Ctrl+S` - Apply draft changes
- `Ctrl+P` - Probe all routes (health check)
- `Ctrl+I` - Run integrity check
- `Ctrl+Q` - Show QR code for selected route
- `Ctrl+B` - Export diagnostic bundle (redacted)
- `Ctrl+Shift+B` - Preview diagnostic bundle

## Log Management
- `0` - Show all log levels
- `1` - Toggle INFO level
- `2` - Toggle WARN level
- `3` - Toggle ERROR level

## Proxy & Configuration
- `E` - External proxy attach/detach
- `Ctrl+X` - Emergency reset (kill owned processes)

## Command Palette Commands
- `/add` - Add a new route
- `/delete` or `/remove` - Delete selected route
- `/qr` - Show QR code
- `/logs` - Switch to Logs tab
- `/probe` - Probe all routes
- `/settings` - Switch to Config tab
- `/help` - Show this help screen

## General
- `Q` - Quit application
- `F1` - Show this help screen
- `Esc` - Close modals/dialogs

## Tips
- **Draft Mode**: Changes are staged until you press `Ctrl+S` to apply
- **Status Indicators**: ● ONLINE (green), ● OFFLINE (red), ● DISABLED (dim)
- **Focus**: Use `Tab` to move between sections, arrows within sections
- **Clipboard**: Y/H/U shortcuts copy different route information
                """,
                id="help-content",
            )
            with Horizontal(id="help-buttons"):
                yield Button("Close", id="close-help", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-help":
            self.dismiss()


class ConfirmDeleteModal(ModalScreen[bool]):
    """Confirmation dialog for deleting a route."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("n", "cancel", "No"),
    ]

    CSS = """
    ConfirmDeleteModal {
        align: center middle;
    }

    #delete-dialog {
        width: 70;
        height: auto;
        border: thick $error;
        background: $surface;
        padding: 2;
    }

    #delete-title {
        text-align: center;
        text-style: bold;
        color: $error;
        margin-bottom: 1;
        padding: 1;
    }

    #delete-message {
        text-align: center;
        padding: 1;
        margin: 1 0 2 0;
    }

    #delete-buttons {
        width: 100%;
        height: 3;
        align: center middle;
    }

    #delete-buttons Button {
        margin: 0 1;
        min-width: 12;
    }
    """

    def __init__(self, route_name: str):
        super().__init__()
        self.route_name = route_name

    def compose(self) -> ComposeResult:
        with Vertical(id="delete-dialog"):
            yield Static("⚠️  Confirm Delete", id="delete-title")
            yield Static(
                f"Are you sure you want to delete route '[bold]{self.route_name}[/bold]'?\n\n"
                "This will remove the route from your configuration (draft mode).\n"
                "Press Ctrl+S to persist the change.",
                id="delete-message",
            )
            with Horizontal(id="delete-buttons"):
                yield Button("Delete", id="confirm-delete", variant="error")
                yield Button("Cancel", id="cancel-delete", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-delete":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)
