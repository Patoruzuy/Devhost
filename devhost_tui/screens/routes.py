"""
Routes screen — primary dashboard view.

Shows the routes DataTable, flow diagram, verify panel, logs,
config snippet, and integrity panel in a tabbed layout.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container

from ..widgets import DetailsPane, StatusGrid

if TYPE_CHECKING:
    from devhost_cli.state import StateConfig

    from ..session import SessionState


class RoutesScreen(Container):
    """Routes management screen — the main dashboard view."""

    def compose(self) -> ComposeResult:
        yield StatusGrid(id="main-grid")
        yield DetailsPane(id="details")

    def refresh_data(
        self,
        session: SessionState | None = None,
        probe_results: dict | None = None,
        integrity_results: dict | None = None,
        state: StateConfig | None = None,
    ) -> None:
        """Refresh routes grid and detail pane from caller-provided state."""
        if session is None:
            return

        probe_results = probe_results or {}

        integrity_ok = None
        if integrity_results is not None:
            integrity_ok = all(ok for ok, _ in integrity_results.values())

        grid = self.query_one(StatusGrid)
        grid.update_routes(
            session.routes,
            session.proxy_mode,
            session.system_domain,
            session.gateway_port,
            probe_results,
            integrity_ok,
        )

        selected = getattr(self.app, "selected_route", None)
        if selected:
            details = self.query_one(DetailsPane)
            route = session.get_route(selected)
            if route:
                details.show_route(
                    selected,
                    route,
                    session,
                    probe_results,
                    integrity_results,
                    state,
                )
