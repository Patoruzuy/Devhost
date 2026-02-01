"""
Devhost CLI - Lightweight local development domain router
Cross-platform Python package for managing local development domains
"""

__version__ = "2.1.0"

from .config import Config
from .factory import create_devhost_app, create_proxy_router, enable_subdomain_routing
from .middleware import DevhostMiddleware
from .router import create_app

__all__ = [
    "Config",
    "create_app",
    "create_devhost_app",
    "create_proxy_router",
    "enable_subdomain_routing",
    "DevhostMiddleware",
    "__version__",
]
