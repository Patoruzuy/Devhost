"""
Subprocess timeout enforcement for security hardening (Phase 4 L-12).

Provides safe subprocess execution with enforced timeouts to prevent
hanging processes and resource exhaustion attacks.

All subprocess calls should use these timeout constants instead of
hard-coded values or no timeout at all.
"""

# Timeout constants (in seconds)
# Based on expected operation duration and security considerations

# Short operations (< 5 seconds)
TIMEOUT_QUICK = 5
"""Quick operations: version checks, simple commands."""

# Standard operations (< 30 seconds)
TIMEOUT_STANDARD = 30
"""Standard operations: start/stop services, file operations, most commands."""

# Long operations (< 60 seconds)
TIMEOUT_LONG = 60
"""Long operations: Caddy validate, complex configurations, network operations."""

# Extended operations (< 120 seconds)
TIMEOUT_EXTENDED = 120
"""Extended operations: Docker builds, package installations."""

# Interactive operations (no timeout)
TIMEOUT_NONE = None
"""Interactive operations: text editors, user input required."""


# Operation-specific timeouts for common devhost operations
TIMEOUTS = {
    # Caddy operations
    "caddy_version": TIMEOUT_QUICK,
    "caddy_validate": TIMEOUT_LONG,      # Can be slow for complex configs
    "caddy_start": TIMEOUT_STANDARD,
    "caddy_stop": TIMEOUT_STANDARD,
    "caddy_reload": TIMEOUT_STANDARD,
    "caddy_fmt": TIMEOUT_STANDARD,
    
    # System operations
    "systemctl": TIMEOUT_STANDARD,
    "sudo": TIMEOUT_STANDARD,
    
    # Windows operations
    "powershell": TIMEOUT_STANDARD,
    "wsl": TIMEOUT_STANDARD,
    "nssm": TIMEOUT_STANDARD,
    "taskkill": TIMEOUT_QUICK,
    
    # Tunnel operations
    "cloudflared_start": TIMEOUT_EXTENDED,  # May need to connect
    "ngrok_start": TIMEOUT_EXTENDED,
    "tunnel_stop": TIMEOUT_STANDARD,
    
    # Certificate operations
    "openssl": TIMEOUT_QUICK,
    
    # Editor operations (interactive)
    "editor": TIMEOUT_NONE,  # Interactive - no timeout
    
    # Browser operations
    "browser_open": TIMEOUT_QUICK,
}


def get_timeout(operation: str, default: int = TIMEOUT_STANDARD) -> int | None:
    """
    Get the recommended timeout for a specific operation.
    
    Args:
        operation: Operation name (e.g., "caddy_start", "systemctl")
        default: Default timeout if operation not found
        
    Returns:
        Timeout in seconds, or None for interactive operations
        
    Examples:
        >>> get_timeout("caddy_version")
        5
        >>> get_timeout("caddy_validate")
        60
        >>> get_timeout("editor")
        None
        >>> get_timeout("unknown_operation")
        30
    """
    return TIMEOUTS.get(operation, default)
