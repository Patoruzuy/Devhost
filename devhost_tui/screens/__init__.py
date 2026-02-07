"""
Devhost TUI Screens - ContentSwitcher-managed screen panels.

Each module provides a Container widget that serves as a "screen"
within the main app's ContentSwitcher.
"""

from .diagnostics import DiagnosticsScreen
from .proxy import ProxyScreen
from .routes import RoutesScreen
from .settings import SettingsScreen
from .tunnels import TunnelsScreen

__all__ = [
    "DiagnosticsScreen",
    "ProxyScreen",
    "RoutesScreen",
    "SettingsScreen",
    "TunnelsScreen",
]
