"""
Utility functions for domain extraction and target parsing.
"""

import os
from pathlib import Path
from urllib.parse import urlparse


def load_domain() -> str:
    """Load the base domain from environment or .devhost/domain file."""
    env_domain = os.getenv("DEVHOST_DOMAIN")
    if env_domain:
        return env_domain.strip().lower()
    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / ".devhost" / "domain",
        here.parent.parent.parent / ".devhost" / "domain",
        here.parent.parent / ".devhost" / "domain",
    ]
    for path in candidates:
        try:
            if path.is_file():
                value = path.read_text().strip().lower()
                if value:
                    return value
        except Exception:
            continue
    return "localhost"


def extract_subdomain(host_header: str | None, base_domain: str | None = None) -> str | None:
    """
    Extract subdomain from Host header.

    Args:
        host_header: HTTP Host header value (may include port)
        base_domain: Base domain to match against (defaults to load_domain())

    Returns:
        Subdomain string or None if invalid/not found
    """
    if not host_header:
        return None
    base_domain = (base_domain or load_domain()).strip(".").lower()
    if not base_domain:
        return None
    # strip port if present
    host_only = host_header.split(":")[0].strip().lower()
    suffix = f".{base_domain}"
    if not host_only.endswith(suffix):
        return None
    sub = host_only[: -len(suffix)]
    if not sub:
        return None
    return sub


def parse_target(value) -> tuple[str, str, int] | None:
    """
    Parse a target value into (scheme, host, port) tuple.

    Supports:
    - int: 8000 -> ("http", "127.0.0.1", 8000)
    - numeric string: "8000" -> ("http", "127.0.0.1", 8000)
    - host:port: "192.168.1.100:8080" -> ("http", "192.168.1.100", 8080)
    - full URL: "http://example.com:8080" -> ("http", "example.com", 8080)

    Args:
        value: Target specification (int, str, or URL)

    Returns:
        (scheme, host, port) tuple or None if invalid
    """
    if value is None:
        return None
    if isinstance(value, int):
        if value > 0:
            return ("http", "127.0.0.1", value)
        return None
    if isinstance(value, str):
        if value.startswith("http://") or value.startswith("https://"):
            parsed = urlparse(value)
            if parsed.hostname and parsed.port:
                return (parsed.scheme, parsed.hostname, parsed.port)
            return None
        if ":" in value:
            host, port = value.rsplit(":", 1)
            if host and port.isdigit():
                return ("http", host, int(port))
            return None
        if value.isdigit():
            port = int(value)
            if port > 0:
                return ("http", "127.0.0.1", port)
            return None
    return None
