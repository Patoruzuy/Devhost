"""
Command provider for Textual's built-in CommandPalette.

Replaces the custom /command input with the native Ctrl+P palette.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.command import Hit, Hits, Provider

if TYPE_CHECKING:
    from .app import DevhostDashboard


class DevhostCommandProvider(Provider):
    """Provide devhost-specific commands to the Textual CommandPalette."""

    async def search(self, query: str) -> Hits:
        """Yield matching commands for the given query."""
        app: DevhostDashboard = self.app  # type: ignore[assignment]
        commands = self._build_commands(app)
        matcher = self.matcher(query)
        for name, help_text, callback in commands:
            score = matcher.match(name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(name),
                    callback,
                    help=help_text,
                )

    def _build_commands(self, app: DevhostDashboard) -> list[tuple[str, str, callable]]:
        """Build the list of available commands."""
        commands = [
            # Navigation
            ("Go to Routes", "Switch to the Routes screen", lambda: app.switch_screen_by_id("routes")),
            ("Go to Tunnels", "Switch to the Tunnels screen", lambda: app.switch_screen_by_id("tunnels")),
            ("Go to Proxy", "Switch to the Proxy screen", lambda: app.switch_screen_by_id("proxy")),
            ("Go to Diagnostics", "Switch to the Diagnostics screen", lambda: app.switch_screen_by_id("diagnostics")),
            ("Go to Settings", "Switch to the Settings screen", lambda: app.switch_screen_by_id("settings")),
            # Route actions
            ("Add Route", "Open the Add Route wizard", app.action_add_route),
            ("Delete Route", "Delete the selected route", app.action_delete_route),
            ("Open Route in Browser", "Open the selected route URL", app.action_open_url),
            ("Copy URL", "Copy the selected route URL to clipboard", app.action_copy_url),
            ("Copy Host", "Copy the selected route Host header", app.action_copy_host),
            ("Copy Upstream", "Copy the selected route upstream target", app.action_copy_upstream),
            # System
            ("Refresh", "Refresh all data from state", app.action_refresh),
            ("Probe Routes", "Run health probes on all routes", app.action_probe_routes),
            ("Integrity Check", "Run integrity check on tracked files", app.action_integrity_check),
            ("Apply Changes", "Persist draft changes to disk", app.action_apply_changes),
            # Diagnostics
            (
                "Export Diagnostics (Redacted)",
                "Export a redacted diagnostic bundle",
                lambda: app.export_diagnostics(redact=True),
            ),
            (
                "Export Diagnostics (Raw)",
                "Export a raw diagnostic bundle",
                lambda: app.export_diagnostics(redact=False),
            ),
            # Features
            ("Show QR Code", "Show QR code for the selected route", app.action_show_qr),
            ("Show Help", "Show keyboard shortcuts and help", app.action_show_help),
            # Danger
            ("Emergency Reset", "Kill owned processes and reset to gateway", app.action_emergency_reset),
        ]
        return commands
