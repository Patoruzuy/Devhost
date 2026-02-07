"""
Enhanced AddRouteWizard - Multi-step wizard with improved UX

This file contains the redesigned Add Route wizard that will replace
the existing AddRouteWizard in modals.py.

Key improvements:
1. Ghost Port Detection (Step 0) - Pre-scan and show detected processes
2. Identity & Target (Step 1) - With async validation indicator
3. Access Method (Step 2) - Simple vs Friendly URL fork
4. Routing Mode (Step 3) - Visual cards for mode selection (if advanced)
5. Review & Trust (Step 4) - Dry-run report with file changes

"""

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ProgressBar, RadioButton, RadioSet, Static

from devhost_cli.scanner import ListeningPort
from devhost_cli.state import StateConfig
from devhost_cli.validation import parse_target, validate_name


class AddRouteWizard(ModalScreen[bool]):
    """
    Multi-step wizard to add a new route.

    Flow:
    Step 0: Ghost Port Detection (auto-scan, show detected processes)
    Step 1: Identity & Target (name + upstream with validation)
    Step 2: Access Method (Simple localhost:PORT vs Friendly URL)
    Step 3: Routing Mode (if Friendly URL, show mode cards)
    Step 4: Review & Trust (dry-run report)
    """

    BINDINGS = [
        Binding("escape", "dismiss_wizard", "Close", show=False),
    ]

    CSS = """
    AddRouteWizard {
        align: center middle;
    }

    #wizard-dialog {
        width: 95%;
        max-width: 120;
        min-width: 80;
        height: 80%;
        max-height: 45;
        min-height: 30;
        border: thick $primary;
        background: $surface;
        padding: 2;
    }

    #wizard-content {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }

    .wizard-step {
        width: 100%;
        margin-bottom: 1;
    }

    .wizard-title {
        width: 100%;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .wizard-step {
        width: 100%;
        margin-bottom: 1;
    }

    .field-label {
        margin-bottom: 0;
        color: $text;
    }

    .field-input {
        margin-bottom: 1;
    }

    .validation-indicator {
        height: 1;
        margin-bottom: 1;
        padding: 0 1;
    }

    #wizard-progress {
        margin-bottom: 1;
    }

    #progress-label {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    .validation-indicator.pending {
        color: $warning;
    }

    .validation-indicator.success {
        color: $success;
    }

    .validation-indicator.error {
        color: $error;
    }

    #port-list {
        height: auto;
        max-height: 12;
        margin: 1 0;
        padding: 1;
        background: $surface-darken-1;
        border: round $primary-darken-2;
        overflow-y: auto;
    }

    .mode-card {
        border: solid $primary-darken-1;
        padding: 1;
        margin: 0 1 1 0;
        background: $surface-darken-1;
        width: 100%;
    }

    .mode-card.selected {
        border: solid $accent;
        background: $primary-darken-3;
    }

    .mode-card-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 0;
    }

    .mode-card-desc {
        color: $text-muted;
    }

    #review-content {
        border: round $primary-darken-2;
        background: $surface-darken-1;
        padding: 1;
        margin: 1 0;
    }

    #wizard-buttons {
        margin-top: 1;
        width: 100%;
        align: right middle;
    }

    #wizard-buttons Button {
        margin: 0 0 0 1;
        min-width: 10;
    }

    RadioSet {
        margin: 1 0;
    }

    .progress-bar {
        height: 1;
        margin-bottom: 1;
        background: $surface-darken-1;
    }
    """

    # Reactive properties for validation state
    validation_status = reactive("idle")  # idle, pending, success, error

    def __init__(self, detected_ports: list[ListeningPort] | None = None, scan_in_progress: bool = False):
        super().__init__()
        self.step = 0  # Start at step 0 (Ghost Port Detection)
        self.route_name = ""
        self.route_upstream = ""
        self.access_method = "simple"  # "simple" or "friendly"
        self.route_mode = "gateway"
        self.detected_ports: list[ListeningPort] = detected_ports or []
        self._scan_in_progress = scan_in_progress

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard-dialog"):
            yield Static("Step 1 of 5", id="progress-label")
            yield ProgressBar(total=5, show_eta=False, id="wizard-progress")
            yield Label("[b]Add Route - Step 0: Ghost Port Detection[/b]", id="wizard-title", classes="wizard-title")
            yield VerticalScroll(id="wizard-content")
            with Horizontal(id="wizard-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Skip", variant="default", id="skip")
                yield Button("Next", variant="primary", id="next")

    def on_mount(self) -> None:
        """Start with Ghost Port Detection."""
        if hasattr(self.app, "get_port_scan_results"):
            ports, in_progress = self.app.get_port_scan_results()
            self.detected_ports = ports
            self._scan_in_progress = in_progress
        self._show_step_0()

    def set_detected_ports(self, ports: list[ListeningPort]) -> None:
        """Update detected ports from background scan."""
        self.detected_ports = ports
        self._scan_in_progress = False
        if self.is_mounted and self.step == 0:
            try:
                port_list = self.query_one("#port-list", Static)
                port_list.update(self._port_list_text())
            except Exception:
                return

    def _port_list_text(self) -> str:
        """Generate port list display text."""
        if self._scan_in_progress and not self.detected_ports:
            return "[yellow]⏳ Scanning for listening ports...[/yellow]"
        if not self.detected_ports:
            return "[dim]No listening ports detected. You can manually enter your target.[/dim]"

        lines = ["[b]Detected listening processes:[/b]\n"]
        for port_info in self.detected_ports[:10]:
            emoji = "🐍" if "python" in port_info.name.lower() else "🟢"
            lines.append(f"{emoji} Port {port_info.port} - {port_info.name} (PID {port_info.pid})")

        if len(self.detected_ports) > 10:
            lines.append(f"\n[dim]... and {len(self.detected_ports) - 10} more[/dim]")

        return "\n".join(lines)

    def _update_progress(self) -> None:
        """Update progress indicator."""
        total_steps = 5 if self.access_method == "friendly" else 4
        current = self.step + 1
        try:
            progress_bar = self.query_one("#wizard-progress", ProgressBar)
            progress_bar.update(total=total_steps, progress=current)

            label = self.query_one("#progress-label", Static)
            label.update(f"Step {current} of {total_steps}")
        except Exception:
            pass

    def _show_step_0(self) -> None:
        """Step 0: Ghost Port Detection - Show detected processes."""
        content = self.query_one("#wizard-content")
        content.remove_children()

        content.mount(
            Static(
                "[cyan]We've scanned your system for running applications. Select one to quick-fill, or proceed manually.[/cyan]",
                classes="wizard-step",
            )
        )
        content.mount(Static(self._port_list_text(), id="port-list"))
        content.mount(
            Static(
                "[dim]Tip: If your app isn't listed, it might not be running yet. Start it first, then come back here.[/dim]",
                classes="wizard-step",
            )
        )

        title = self.query_one("#wizard-title")
        title.update("[b]Add Route - Step 0: Ghost Port Detection[/b]")

        self._update_progress()

        # Show Skip button for this step
        try:
            skip_btn = self.query_one("#skip", Button)
            skip_btn.display = True
        except Exception:
            pass

    def _show_step_1(self) -> None:
        """Step 1: Identity & Target with async validation."""
        content = self.query_one("#wizard-content")
        content.remove_children()

        content.mount(
            Static(
                "[cyan]Give your route a name and specify the upstream target (where your app is listening).[/cyan]",
                classes="wizard-step",
            )
        )

        # Route name input
        content.mount(Label("Route Name (subdomain):", classes="field-label"))
        content.mount(Input(placeholder="e.g., api, web, dashboard", id="name-input", classes="field-input"))
        content.mount(Static("", id="name-validation", classes="validation-indicator"))

        # Upstream input
        content.mount(Label("Upstream Target:", classes="field-label"))
        content.mount(
            Input(
                placeholder="e.g., 8000, 127.0.0.1:8000, or http://localhost:8000",
                id="upstream-input",
                classes="field-input",
            )
        )
        content.mount(Static("", id="upstream-validation", classes="validation-indicator"))

        title = self.query_one("#wizard-title")
        title.update("[b]Add Route - Step 1: Identity & Target[/b]")

        self._update_progress()

        # Hide Skip button
        try:
            skip_btn = self.query_one("#skip", Button)
            skip_btn.display = False
        except Exception:
            pass

    def _show_step_2(self) -> None:
        """Step 2: Access Method (Simple vs Friendly URL)."""
        content = self.query_one("#wizard-content")
        content.remove_children()

        content.mount(Static("[cyan]Choose how you want to access your route.[/cyan]", classes="wizard-step"))

        content.mount(Label("Access Method:", classes="field-label"))
        content.mount(
            RadioSet(
                RadioButton(
                    "🟢 Simple (localhost:PORT) - Direct access, no DNS needed",
                    id="access-simple",
                    value=True,
                ),
                RadioButton(
                    "🌐 Friendly URL (Advanced) - Custom domain routing (e.g., api.localhost)",
                    id="access-friendly",
                ),
                id="access-select",
            )
        )

        content.mount(
            Static(
                "\n[b]Simple:[/b] Best for quick testing. Access via browser at http://name.localhost:7777\n"
                "[b]Friendly URL:[/b] Production-like URLs. Requires routing mode selection.",
                classes="wizard-step",
            )
        )

        title = self.query_one("#wizard-title")
        title.update("[b]Add Route - Step 2: Access Method[/b]")

        self._update_progress()

    def _show_step_3(self) -> None:
        """Step 3: Routing Mode (only if Friendly URL was chosen)."""
        content = self.query_one("#wizard-content")
        content.remove_children()

        state = getattr(self.app, "session", None) or StateConfig()

        content.mount(
            Static("[cyan]Select how Devhost should route traffic to your application.[/cyan]", classes="wizard-step")
        )

        # Mode A: Gateway
        with Vertical(classes="mode-card"):
            content.mount(Label("🔷 Gateway Mode (Recommended)", classes="mode-card-title"))
            content.mount(
                Static(
                    f"Local only. Routes through port {state.gateway_port}. No DNS or TLS setup required.\n"
                    f"URL: http://{self.route_name}.localhost:{state.gateway_port}",
                    classes="mode-card-desc",
                )
            )
            content.mount(RadioButton("Select Gateway", id="mode-gateway", value=True))

        # Mode B: System
        with Vertical(classes="mode-card"):
            content.mount(Label("🔶 System Mode", classes="mode-card-title"))
            content.mount(
                Static(
                    "Custom domain with local TLS on ports 80/443. Requires one-time admin setup.\n"
                    f"URL: https://{self.route_name}.localhost",
                    classes="mode-card-desc",
                )
            )
            content.mount(RadioButton("Select System", id="mode-system"))

        # Mode C: External
        with Vertical(classes="mode-card"):
            content.mount(Label("🔸 External Mode", classes="mode-card-title"))
            content.mount(
                Static(
                    "Integration with your existing Caddy/Nginx/Traefik proxy. Devhost generates snippets.\n"
                    f"URL: http://{self.route_name}.localhost (via your proxy)",
                    classes="mode-card-desc",
                )
            )
            content.mount(RadioButton("Select External", id="mode-external"))

        title = self.query_one("#wizard-title")
        title.update("[b]Add Route - Step 3: Routing Mode[/b]")

        self._update_progress()

    def _show_step_4(self) -> None:
        """Step 4: Review & Trust - Dry run report."""
        content = self.query_one("#wizard-content")
        content.remove_children()

        state = getattr(self.app, "session", None) or StateConfig()

        # Build dry-run report
        review_lines = [
            "[b cyan]Configuration Review[/b]\n",
            f"[b]Route Name:[/b] {self.route_name}",
            f"[b]Upstream:[/b] {self.route_upstream}",
            f"[b]Access Method:[/b] {self.access_method.capitalize()}",
            f"[b]Routing Mode:[/b] {self.route_mode.capitalize()}",
            f"[b]Domain:[/b] {state.system_domain}\n",
        ]

        # Show URL
        if self.route_mode == "gateway" or self.access_method == "simple":
            url = f"http://{self.route_name}.{state.system_domain}:{state.gateway_port}"
        else:
            url = (
                f"https://{self.route_name}.{state.system_domain}"
                if self.route_mode == "system"
                else f"http://{self.route_name}.{state.system_domain}"
            )

        review_lines.append(f"[b]Your URL:[/b] [link={url}]{url}[/link]\n")

        # File changes
        review_lines.append("[b yellow]This wizard will:[/b]")
        review_lines.append("  ✓ Write to: ~/.devhost/state.yml")

        if self.route_mode == "system":
            from devhost_cli.caddy_lifecycle import get_caddyfile_path

            caddyfile = get_caddyfile_path(state)
            review_lines.append(f"  ✓ Generate: {caddyfile}")
        elif self.route_mode == "external":
            review_lines.append(f"  ✓ Generate snippet: ~/.devhost/snippets/{self.route_name}.conf")

        review_lines.append("  ✓ Enable drift protection (integrity hashing)")
        review_lines.append("\n[yellow]⚠️ Backup copies will be created before any file modifications.[/yellow]")

        content.mount(Static("\n".join(review_lines), id="review-content"))

        title = self.query_one("#wizard-title")
        title.update("[b]Add Route - Step 4: Review & Apply[/b]")

        self._update_progress()

        # Update button
        next_btn = self.query_one("#next", Button)
        next_btn.label = "Apply Configuration"
        next_btn.variant = "success"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(False)
        elif event.button.id == "skip":
            self._advance_step()
        elif event.button.id == "next":
            self._advance_step()

    def action_dismiss_wizard(self) -> None:
        """Handle ESC key to close wizard."""
        self.dismiss(False)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Real-time validation as user types."""
        if event.input.id == "name-input":
            self._validate_name_async(event.value)
        elif event.input.id == "upstream-input":
            self._validate_upstream_async(event.value)

    @work(exclusive=True)
    async def _validate_name_async(self, value: str) -> None:
        """Async name validation with visual feedback."""
        indicator = self.query_one("#name-validation", Static)
        name = value.strip().lower()

        if not name:
            indicator.update("")
            indicator.remove_class("pending", "success", "error")
            return

        indicator.update("⏳ Validating...")
        indicator.add_class("pending")
        indicator.remove_class("success", "error")

        # Simulate async validation
        import asyncio

        await asyncio.sleep(0.3)

        if not validate_name(name):
            indicator.update("❌ Invalid name. Use letters, numbers, and hyphens.")
            indicator.remove_class("pending")
            indicator.add_class("error")
        else:
            indicator.update("✅ Valid name")
            indicator.remove_class("pending")
            indicator.add_class("success")

    @work(exclusive=True)
    async def _validate_upstream_async(self, value: str) -> None:
        """Async upstream validation with visual feedback."""
        indicator = self.query_one("#upstream-validation", Static)
        upstream = value.strip()

        if not upstream:
            indicator.update("")
            indicator.remove_class("pending", "success", "error")
            return

        indicator.update("⏳ Validating...")
        indicator.add_class("pending")
        indicator.remove_class("success", "error")

        # Simulate async validation
        import asyncio

        await asyncio.sleep(0.3)

        if not parse_target(upstream):
            indicator.update("❌ Invalid target. Use: <port>, <host>:<port>, or http(s)://<host>:<port>")
            indicator.remove_class("pending")
            indicator.add_class("error")
        else:
            indicator.update("✅ Valid target")
            indicator.remove_class("pending")
            indicator.add_class("success")

    def _advance_step(self) -> None:
        """Advance to the next step with validation."""
        if self.step == 0:
            # Skip to step 1
            self.step = 1
            self._show_step_1()

        elif self.step == 1:
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
                    "Invalid upstream. Use <port>, <host>:<port>, or http(s)://<host>:<port>.",
                    severity="error",
                )
                return

            # Normalize upstream
            if self.route_upstream.isdigit():
                self.route_upstream = f"127.0.0.1:{self.route_upstream}"

            self.step = 2
            self._show_step_2()

        elif self.step == 2:
            # Get access method
            access_select = self.query_one("#access-select", RadioSet)
            if access_select.pressed_button:
                button_id = access_select.pressed_button.id
                if button_id == "access-simple":
                    self.access_method = "simple"
                    self.route_mode = "gateway"  # Simple always uses gateway
                    # Skip step 3, go directly to review
                    self.step = 4
                    self._show_step_4()
                elif button_id == "access-friendly":
                    self.access_method = "friendly"
                    self.step = 3
                    self._show_step_3()

        elif self.step == 3:
            # Get routing mode
            try:
                gateway_btn = self.query_one("#mode-gateway", RadioButton)
                system_btn = self.query_one("#mode-system", RadioButton)
                external_btn = self.query_one("#mode-external", RadioButton)

                if gateway_btn.value:
                    self.route_mode = "gateway"
                elif system_btn.value:
                    self.route_mode = "system"
                elif external_btn.value:
                    self.route_mode = "external"
            except Exception:
                self.route_mode = "gateway"

            self.step = 4
            self._show_step_4()

        elif self.step == 4:
            # Apply configuration
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

        self.app.notify(f"Route '{self.route_name}' added (draft). Press Ctrl+S to apply.", severity="information")
        if hasattr(self.app, "refresh_data"):
            self.app.refresh_data()
