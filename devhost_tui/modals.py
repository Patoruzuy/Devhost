"""
Devhost TUI - Modal Dialogs

Contains modal screens for:
- AddRouteWizard: Multi-step wizard to add a new route
- ConfirmResetModal: Emergency reset confirmation
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static

from devhost_cli.state import StateConfig
from devhost_cli.validation import parse_target, validate_name

from .scanner import ListeningPort, detect_framework, scan_listening_ports


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

        state = StateConfig()

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

    def __init__(self):
        super().__init__()
        self.step = 0
        self.route_name = ""
        self.route_upstream = ""
        self.route_mode = "gateway"
        self.detected_ports: list[ListeningPort] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard-dialog"):
            yield Label("[b]Add Route - Step 1: Identity[/b]", id="wizard-title", classes="wizard-title")
            yield Container(id="wizard-content")
            with Horizontal(id="wizard-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Next", variant="primary", id="next")

    def on_mount(self) -> None:
        """Scan for ports and show first step."""
        self.detected_ports = scan_listening_ports()
        self._show_step_1()

    def _show_step_1(self) -> None:
        """Show step 1: Identity & Target."""
        content = self.query_one("#wizard-content")
        content.remove_children()

        # Detected ports section
        if self.detected_ports:
            port_text = "Detected listening ports:\n"
            for p in self.detected_ports[:8]:  # Limit to 8
                framework = detect_framework(p.name, p.port)
                if framework:
                    port_text += f"  {p.port}  {p.name}  [{framework}]\n"
                else:
                    port_text += f"  {p.port}  {p.name}\n"
            content.mount(Static(port_text, id="port-list"))

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

        state = StateConfig()

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

        state = StateConfig()

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
        state = StateConfig()

        # Add the route
        state.set_route(
            self.route_name,
            self.route_upstream,
            domain=state.system_domain,
            enabled=True,
        )

        # Apply selected routing mode and update proxy config
        state.proxy_mode = self.route_mode

        if self.route_mode == "system":
            from devhost_cli.caddy_lifecycle import write_system_caddyfile

            write_system_caddyfile(state)
        elif self.route_mode == "external":
            from devhost_cli.proxy import export_snippets

            state.set_external_config(state.external_driver)
            export_snippets(state, [state.external_driver])

        self.app.notify(f"Route '{self.route_name}' added", severity="information")
        self.app.refresh_data()
