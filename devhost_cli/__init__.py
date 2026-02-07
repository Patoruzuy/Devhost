"""
Devhost CLI - Lightweight local development domain router
Cross-platform Python package for managing local development domains
"""

__version__ = "3.0.0-alpha.1"

from .config import Config, ProjectConfig
from .router_manager import Router
from .runner import DevhostRunner, run
from .scanner import ListeningPort, detect_framework, format_port_list, scan_listening_ports
from .state import StateConfig

__all__ = [
    "Config",
    "ProjectConfig",
    "Router",
    "DevhostRunner",
    "run",
    "StateConfig",
    "ListeningPort",
    "scan_listening_ports",
    "detect_framework",
    "format_port_list",
    "__version__",
]
