"""
Devhost TUI - Modal Dialogs

Contains modal screens for:
- AddRouteWizard: Multi-step wizard to add a new route
- ConfirmResetModal: Emergency reset confirmation
- ExternalProxyModal: Attach/detach external proxy configs
"""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static

from devhost_cli.state import StateConfig
from devhost_cli.validation import parse_target, validate_name

from .scanner import ListeningPort, format_port_list


class ExternalProxyModal(ModalScreen[bool]):
    """Attach/detach devhost snippets to an external proxy config."""

    CSS = """
    ExternalProxyModal {
        align: center middle;
    }

    #external-dialog {
        width: 90;
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
            yield Static("Discover a config file to prefill the path.", id="discover-results")
            yield Static("Reload hint will appear here.", id="reload-hint")
            with Horizontal(id="external-buttons"):
                yield Button("Discover", variant="default", id="discover")
                yield Button("Export Snippet", variant="primary", id="export")
                yield Button("Attach", variant="success", id="attach")
                yield Button("Detach", variant="warning", id="detach")
                yield Button("Show Reload Hint", variant="default", id="reload")
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

    def _update_discover_text(self, message: str) -> None:
        discover = self.query_one("#discover-results", Static)
        discover.update(message)

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
        from devhost_cli.proxy import attach_to_config, detach_from_config, discover_proxy_config, export_snippets

        if event.button.id == "close":
            self.dismiss(False)
            return

        driver = self._selected_driver()

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
            exported = export_snippets(state, [driver])
            snippet_path = exported.get(driver)
            if snippet_path:
                self.app.notify(f"Snippet exported: {snippet_path}", severity="information")
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
            success, msg = attach_to_config(state, config_path, driver)
            self.app.notify(msg, severity="information" if success else "error")
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
            if success:
                self._refresh_state()
            return


class DiagnosticsPreviewModal(ModalScreen[bool]):
    """Preview diagnostic bundle contents."""

    CSS = """
    DiagnosticsPreviewModal {
        align: center middle;
    }

    #diagnostics-preview {
        width: 90;
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
            self.dismiss(True)


class IntegrityDiffModal(ModalScreen[bool]):
    """Show unified diff for integrity drift."""

    CSS = """
    IntegrityDiffModal {
        align: center middle;
    }

    #integrity-diff {
        width: 100;
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


class AddRouteWizard(ModalScreen[bool]):
    """Multi-step wizard to add a new route."""

    CSS = """
    AddRouteWizard {
        align: center middle;
    }

    #wizard-dialog {
        width: 80;
        height: auto;
        min-height: 20;
        border: thick $primary;
        background: $surface;
        padding: 2;
    }

    .wizard-title {
        width: 100%;
        text-style: bold;
        margin-bottom: 1;
    }

    .wizard-step {
        width: 100%;
        margin-bottom: 1;
    }

    .field-label {
        margin-bottom: 0;
    }

    .field-input {
        margin-bottom: 1;
    }

    #port-list {
        height: auto;
        max-height: 10;
        margin: 1 0;
        padding: 1;
        background: $surface-darken-1;
        border: round $primary-darken-2;
    }

    #wizard-buttons {
        margin-top: 2;
        width: 100%;
        align: right middle;
    }

    #wizard-buttons Button {
        margin: 0 1;
    }

    RadioSet {
        margin: 1 0;
    }
    """

    def __init__(self, detected_ports: list[ListeningPort] | None = None, scan_in_progress: bool = False):
        super().__init__()
        self.step = 0
        self.route_name = ""
        self.route_upstream = ""
        self.route_mode = "gateway"
        self.detected_ports: list[ListeningPort] = detected_ports or []
        self._scan_in_progress = scan_in_progress

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard-dialog"):
            yield Label("[b]Add Route - Step 1: Identity[/b]", id="wizard-title", classes="wizard-title")
            yield Container(id="wizard-content")
            with Horizontal(id="wizard-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Next", variant="primary", id="next")

    def on_mount(self) -> None:
        """Scan for ports and show first step."""
        if hasattr(self.app, "get_port_scan_results"):
            ports, in_progress = self.app.get_port_scan_results()
            self.detected_ports = ports
            self._scan_in_progress = in_progress
        self._show_step_1()

    def _port_list_text(self) -> str:
        if self._scan_in_progress and not self.detected_ports:
            return "Scanning for listening ports..."
        if not self.detected_ports:
            return "No listening ports found."
        return "Detected listening ports:\n" + format_port_list(self.detected_ports[:8])

    def set_detected_ports(self, ports: list[ListeningPort]) -> None:
        self.detected_ports = ports
        self._scan_in_progress = False
        if self.is_mounted and self.step == 0:
            try:
                port_list = self.query_one("#port-list", Static)
                port_list.update(self._port_list_text())
            except Exception:
                return

    def _show_step_1(self) -> None:
        """Show step 1: Identity & Target."""
        content = self.query_one("#wizard-content")
        content.remove_children()

        content.mount(Static(self._port_list_text(), id="port-list"))

        # Route name input
        content.mount(Label("Route Name (subdomain):", classes="field-label"))
        content.mount(Input(placeholder="e.g., api, web, dashboard", id="name-input", classes="field-input"))

        # Upstream input
        content.mount(Label("Upstream Target:", classes="field-label"))
        content.mount(Input(placeholder="e.g., 8000 or 127.0.0.1:8000", id="upstream-input", classes="field-input"))

        # Update title
        title = self.query_one("#wizard-title")
        title.update("[b]Add Route - Step 1: Identity[/b]")

    def _show_step_2(self) -> None:
        """Show step 2: Access Mode."""
        content = self.query_one("#wizard-content")
        content.remove_children()

        state = getattr(self.app, "session", None) or StateConfig()

        content.mount(Label("Select routing mode:", classes="field-label"))
        content.mount(
            RadioSet(
                RadioButton(
                    f"Gateway (recommended) - Routes through port {state.gateway_port}",
                    id="mode-gateway",
                    value=True,
                ),
                RadioButton("System - Portless URLs on port 80/443 (requires install)", id="mode-system"),
                RadioButton("External - Integrate with existing proxy", id="mode-external"),
                id="mode-select",
            )
        )

        # Update title
        title = self.query_one("#wizard-title")
        title.update("[b]Add Route - Step 2: Mode[/b]")

        # Update button
        next_btn = self.query_one("#next", Button)
        next_btn.label = "Next"

    def _show_step_3(self) -> None:
        """Show step 3: Review & Confirm."""
        content = self.query_one("#wizard-content")
        content.remove_children()

        state = getattr(self.app, "session", None) or StateConfig()

        # Build review text
        review = f"""
[b]Review Configuration[/b]

Route Name:  {self.route_name}
Upstream:    {self.route_upstream}
Mode:        {self.route_mode}
Domain:      {state.system_domain}

[b]This will:[/b]
  • Write to: ~/.devhost/state.yml
"""
        if self.route_mode == "system":
            from devhost_cli.caddy_lifecycle import get_caddyfile_path

            review += f"  • Generate: {get_caddyfile_path(state)}\n"
        elif self.route_mode == "external":
            review += f"  • Generate: {state.snippet_path}\n"
        else:
            review += "  • No proxy snippet needed (gateway mode)\n"

        review += """  • Enable integrity hashing

[b]URL:[/b]
"""
        if self.route_mode == "gateway":
            review += f"  http://{self.route_name}.{state.system_domain}:{state.gateway_port}"
        else:
            review += f"  http://{self.route_name}.{state.system_domain}"

        content.mount(Static(review))

        # Update title
        title = self.query_one("#wizard-title")
        title.update("[b]Add Route - Step 3: Review[/b]")

        # Update button
        next_btn = self.query_one("#next", Button)
        next_btn.label = "Apply"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(False)
        elif event.button.id == "next":
            self._advance_step()

    def _advance_step(self) -> None:
        """Advance to the next step."""
        if self.step == 0:
            # Validate step 1
            name_input = self.query_one("#name-input", Input)
            upstream_input = self.query_one("#upstream-input", Input)

            self.route_name = name_input.value.strip().lower()
            self.route_upstream = upstream_input.value.strip()

            if not self.route_name:
                self.app.notify("Route name is required", severity="error")
                return
            if not validate_name(self.route_name):
                self.app.notify("Invalid route name. Use letters, numbers, and hyphens.", severity="error")
                return
            if not self.route_upstream:
                self.app.notify("Upstream target is required", severity="error")
                return

            if not parse_target(self.route_upstream):
                self.app.notify(
                    "Invalid upstream target. Use <port>, <host>:<port>, or http(s)://<host>:<port>.",
                    severity="error",
                )
                return

            # Normalize upstream for portability
            if self.route_upstream.isdigit():
                self.route_upstream = f"127.0.0.1:{self.route_upstream}"

            self.step = 1
            self._show_step_2()

        elif self.step == 1:
            # Get selected mode
            mode_select = self.query_one("#mode-select", RadioSet)
            if mode_select.pressed_button:
                button_id = mode_select.pressed_button.id
                if button_id == "mode-gateway":
                    self.route_mode = "gateway"
                elif button_id == "mode-system":
                    self.route_mode = "system"
                elif button_id == "mode-external":
                    self.route_mode = "external"

            self.step = 2
            self._show_step_3()

        elif self.step == 2:
            # Apply the configuration
            self._apply_route()
            self.dismiss(True)

    def _apply_route(self) -> None:
        """Apply the route configuration."""
        if hasattr(self.app, "queue_route_change"):
            self.app.queue_route_change(self.route_name, self.route_upstream, self.route_mode)
        else:
            state = StateConfig()
            state.set_route(
                self.route_name,
                self.route_upstream,
                domain=state.system_domain,
                enabled=True,
            )
            state.proxy_mode = self.route_mode

        self.app.notify(f"Route '{self.route_name}' added (draft)", severity="information")
        self.app.refresh_data()
