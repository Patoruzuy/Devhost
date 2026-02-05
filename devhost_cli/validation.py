"""Target validation and parsing utilities"""

import logging
import re
from urllib.parse import urlparse

from .utils import msg_error, msg_info, msg_warning

logger = logging.getLogger("devhost.validation")

# Security: Only allow http/https schemes
ALLOWED_SCHEMES = {"http", "https"}


def validate_name(name: str) -> bool:
    """Validate mapping name"""
    if not name:
        msg_error("Name cannot be empty")
        return False

    # Only alphanumeric and hyphens
    if not all(c.isalnum() or c == "-" for c in name):
        msg_error("Name must contain only letters, numbers, and hyphens")
        return False

    # Max length
    if len(name) > 63:
        msg_error("Name too long (max 63 characters)")
        return False

    return True


def validate_port(port: int) -> bool:
    """Validate port number"""
    if port < 1 or port > 65535:
        msg_error("Port must be between 1 and 65535")
        return False

    if port < 1024:
        msg_warning(f"Port {port} requires elevated privileges")

    return True


def validate_ip(ip: str) -> bool:
    """Validate IP address format (IPv4)"""
    pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    if not re.match(pattern, ip):
        return False
    # Check each octet is 0-255
    octets = ip.split(".")
    return all(0 <= int(octet) <= 255 for octet in octets)


def parse_target(value: str) -> tuple[str, str, int] | None:
    """
    Parse target value into (scheme, host, port)
    Accepts: 8000, localhost:8000, 192.168.1.100:8000, http://host:port, https://host:port
    """
    if not value:
        return None

    # Just a port number
    if value.isdigit():
        port = int(value)
        if not validate_port(port):
            return None
        return ("http", "127.0.0.1", port)

    # Full URL
    if "://" in value:
        try:
            parsed = urlparse(value)
            
            # Security: Validate scheme
            if parsed.scheme not in ALLOWED_SCHEMES:
                logger.warning("Rejected disallowed scheme: %s", parsed.scheme)
                msg_error(f"Invalid scheme '{parsed.scheme}': only http/https allowed")
                return None
            
            if not parsed.hostname or not parsed.port:
                msg_error("Invalid URL: must include host and port")
                return None
            return (parsed.scheme, parsed.hostname, parsed.port)
        except Exception as e:
            msg_error(f"Invalid URL: {e}")
            return None

    # host:port format
    if ":" in value:
        parts = value.rsplit(":", 1)
        if len(parts) == 2 and parts[1].isdigit():
            host, port_str = parts
            port = int(port_str)
            if not validate_port(port):
                return None
            return ("http", host, port)

    msg_error(f"Invalid target format: {value}")
    msg_info("Use: <port> or <host>:<port> or http(s)://<host>:<port>")
    return None


def get_dev_scheme(value) -> str:
    """Extract scheme from target value"""
    if isinstance(value, str):
        if value.startswith("https://"):
            return "https"
        if value.startswith("http://"):
            return "http"
    return "http"
