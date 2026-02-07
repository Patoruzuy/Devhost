"""
Diagnostics screen — export/preview diagnostic bundles.

Also shows router status and system information.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Label, Static

from ..cli_bridge import DiagnosticsBridge, RouterBridge

if TYPE_CHECKING:
    from ..app import DevhostDashboard


class DiagnosticsScreen(Container):
    """Diagnostics and system health screen."""

    def compose(self) -> ComposeResult:
        yield Label("[b]🩺 Diagnostics[/b]", classes="section-title")
        with VerticalScroll(id="diag-scroll"):
            # -- Router Status --
            yield Label("[b]Router Status[/b]", classes="subsection-title")
            yield Static("Loading...", id="router-status")

            # -- System Info --
            yield Label("[b]System Info[/b]", classes="subsection-title")
            yield Static("Loading...", id="system-info")

            # -- Integrity --
            yield Label("[b]Integrity[/b]", classes="subsection-title")
            yield Static("Loading...", id="integrity-summary")
            with Horizontal(id="integrity-actions"):
                yield Button("Run Integrity Check", id="diag-integrity", variant="default")

            # -- Diagnostic Bundle --
            yield Label("[b]Diagnostic Bundle[/b]", classes="subsection-title")
            yield Static(
                "[dim]Export a diagnostic bundle for sharing or troubleshooting.[/dim]",
                id="bundle-desc",
            )
            with Horizontal(id="bundle-actions"):
                yield Button("Export (Redacted)", id="diag-export-redacted", variant="primary")
                yield Button("Export (Raw)", id="diag-export-raw", variant="warning")
                yield Button("Preview", id="diag-preview", variant="default")
            yield Static("", id="bundle-result")

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        self._load_router_status()
        self._load_system_info()
        self._load_integrity()

    @work(exclusive=True)
    async def _load_router_status(self) -> None:
        running, pid = await RouterBridge.is_running()
        healthy = await RouterBridge.health_check() if running else False

        status_parts = []
        if running:
            status_parts.append(f"[green]● Running[/green] (PID {pid})")
            status_parts.append(f"Health: {'[green]OK[/green]' if healthy else '[red]Unhealthy[/red]'}")
            try:
                import psutil

                proc = psutil.Process(pid)
                uptime = time.time() - proc.create_time()
                status_parts.append(f"Uptime: {self._format_duration(uptime)}")
            except Exception:
                pass
        else:
            status_parts.append("[red]● Stopped[/red]")

        self.query_one("#router-status", Static).update("\n".join(status_parts))

    def _load_system_info(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        session = app.session

        info_lines = [
            f"Proxy Mode: {session.proxy_mode}",
            f"Domain: {session.system_domain}",
            f"Gateway Port: {session.gateway_port}",
            f"Gateway Listen: {session.gateway_listen}",
        ]
        if session.proxy_mode == "external":
            info_lines.append(f"External Driver: {session.external_driver}")
            if session.external_config_path:
                info_lines.append(f"External Config: {session.external_config_path}")
        probe_svc = getattr(app, "probe_service", None)
        if probe_svc and probe_svc.last_probe_time:
            info_lines.append(f"Last Probe: {time.strftime('%H:%M:%S', time.localtime(probe_svc.last_probe_time))}")
        self.query_one("#system-info", Static).update("\n".join(info_lines))

    def _load_integrity(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        results = app.integrity_results
        if results is None:
            self.query_one("#integrity-summary", Static).update("[dim]Not checked yet.[/dim]")
            return
        total = len(results)
        issues = sum(1 for ok, _ in results.values() if not ok)
        if issues:
            text = f"[yellow]{issues} issue(s)[/yellow] out of {total} tracked file(s)"
        else:
            text = f"[green]All {total} file(s) OK[/green]"
        self.query_one("#integrity-summary", Static).update(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "diag-integrity":
            self._run_integrity()
        elif event.button.id == "diag-export-redacted":
            self._export_bundle(redact=True)
        elif event.button.id == "diag-export-raw":
            self._export_bundle(redact=False)
        elif event.button.id == "diag-preview":
            self._preview_bundle()

    @work(exclusive=True)
    async def _run_integrity(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        results = app.state.check_all_integrity()
        app.integrity_results = results
        issues = sum(1 for ok, _ in results.values() if not ok)
        if issues:
            app.notify(f"Integrity issues: {issues} file(s)", severity="warning")
        else:
            app.notify("All files OK", severity="information")
        self._load_integrity()

    @work(exclusive=True)
    async def _export_bundle(self, redact: bool = True) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        label = "redacted" if redact else "raw"
        if not redact:
            app.notify("Raw bundle may contain secrets.", severity="warning")
        app.notify(f"Building diagnostic bundle ({label})...", severity="information")

        success, bundle_path, manifest = await DiagnosticsBridge.export_bundle(app.state, redact=redact)
        if success and bundle_path:
            count = len(manifest.get("included", []))
            redacted_count = len(manifest.get("redacted", []))
            msg = f"Bundle saved: {bundle_path} ({count} files, {redacted_count} redacted)"
            app.notify(msg, severity="information")
            self.query_one("#bundle-result", Static).update(msg)
        else:
            error = manifest.get("error", "unknown error")
            msg = f"Bundle failed: {error}"
            app.notify(msg, severity="error")
            self.query_one("#bundle-result", Static).update(msg)

    @work(exclusive=True)
    async def _preview_bundle(self) -> None:
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        app.notify("Building diagnostics preview...", severity="information")
        preview = await DiagnosticsBridge.preview_bundle(app.state)
        from ..modals import DiagnosticsPreviewModal

        app.push_screen(DiagnosticsPreviewModal(preview))

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = int(seconds)
        mins, secs = divmod(seconds, 60)
        hours, mins = divmod(mins, 60)
        if hours:
            return f"{hours}h {mins}m"
        if mins:
            return f"{mins}m {secs}s"
        return f"{secs}s"
