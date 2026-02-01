"""
Devhost CLI - Lightweight local development domain router
Cross-platform Python package for managing local development domains
"""

__version__ = "2.0.0"

from .config import Config
from .router_manager import Router

__all__ = ["Config", "Router", "__version__"]
