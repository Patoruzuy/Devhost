"""
Executable path validation for security hardening (Phase 4 L-11).

Validates that executables used in subprocess calls are safe:
- Exist on the filesystem
- Are actually executable
- Are not in user-writable locations (security risk)

This prevents attacks where malicious users could replace trusted executables
with compromised versions in user-writable directories.
"""

import os
import shutil
import stat
import sys
from pathlib import Path

# System directories considered safe for executable files
# These are typically read-only for non-admin users
SAFE_EXECUTABLE_DIRS = {
    # Unix/Linux/macOS system paths
    "/bin",
    "/usr/bin",
    "/usr/local/bin",
    "/sbin",
    "/usr/sbin",
    "/opt/homebrew/bin",  # Homebrew on Apple Silicon
    "/usr/local/opt",  # Homebrew traditional
    # Windows system paths
    r"C:\Windows\System32",
    r"C:\Windows\SysWOW64",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
}


def is_user_writable(path: Path) -> tuple[bool, str | None]:
    """
    Check if a path is in a user-writable location.

    Returns (True, reason) if the path is potentially unsafe (user can modify it).
    Returns (False, None) if the path is in a system-controlled location.

    Args:
        path: Path to check

    Returns:
        (is_writable, reason): Tuple of (bool, optional reason string)
    """
    try:
        path_str = str(path.resolve())

        # On Unix systems, check actual file permissions and ownership
        if sys.platform != "win32":
            path_stat = path.stat()
            mode = path_stat.st_mode

            # If owned by current user, treat as user-writable regardless of location
            if path_stat.st_uid == os.getuid():
                return True, "File is owned by current user"

            # If world-writable or group-writable, consider unsafe
            if mode & stat.S_IWOTH:  # World-writable
                return True, "File is world-writable"
            if mode & stat.S_IWGRP:  # Group-writable
                return True, "File is group-writable"

            # If user can write the file directly, consider unsafe
            if os.access(path, os.W_OK):
                return True, "File is writable by current user"

            # If any parent directory is user-writable and not sticky, consider unsafe
            for parent in [path.parent, *path.parents]:
                try:
                    parent_stat = parent.stat()
                except (OSError, PermissionError):
                    continue
                if os.access(parent, os.W_OK):
                    # Sticky bit (e.g., /tmp) reduces replacement risk for non-owned files
                    if not (parent_stat.st_mode & stat.S_ISVTX):
                        return True, f"Parent directory is writable: {parent}"

        # On Windows, check if in user profile directory
        if sys.platform == "win32":
            userprofile = os.environ.get("USERPROFILE", "")
            if userprofile and path_str.startswith(userprofile):
                return True, "File is in user profile directory"

        # Check if in a known safe directory (only after writability checks)
        for safe_dir in SAFE_EXECUTABLE_DIRS:
            if path_str.startswith(safe_dir):
                return False, None

        # Default to safe if we can't determine otherwise
        return False, None

    except (OSError, PermissionError) as e:
        # If we can't stat the file, assume it's unsafe
        return True, f"Cannot stat file: {e}"


def validate_executable(executable_path: str, check_writability: bool = True) -> tuple[bool, str | None]:
    """
    Validate that an executable path is safe to use in subprocess calls.

    Checks:
    1. File exists
    2. File is executable
    3. File is not in a user-writable location (optional)

    Args:
        executable_path: Path to executable (absolute or in PATH)
        check_writability: Whether to check if path is user-writable

    Returns:
        (is_valid, error_message):
        - (True, None) if valid
        - (False, "error description") if invalid

    Examples:
        >>> validate_executable("/usr/bin/python3")
        (True, None)

        >>> validate_executable("~/malicious/caddy")
        (False, "Executable is in a user-writable location: /home/user/malicious/caddy")

        >>> validate_executable("/nonexistent")
        (False, "Executable not found: /nonexistent")
    """
    # Handle empty or None input
    if not executable_path:
        return False, "Executable path is empty"

    try:
        # Resolve to absolute path (support PATH lookup and ~ expansion)
        expanded = os.path.expanduser(executable_path)
        candidate = Path(expanded)
        if candidate.is_absolute() or candidate.parent != Path("."):
            path = candidate.resolve()
        else:
            resolved = find_executable_in_path(executable_path) or shutil.which(executable_path)
            if resolved:
                path = Path(resolved).resolve()
            else:
                path = candidate.resolve()

        # Check existence
        if not path.exists():
            return False, f"Executable not found: {executable_path}"

        # Check if it's a file (not a directory)
        if not path.is_file():
            return False, f"Path is not a file: {executable_path}"

        # Check if executable
        if not os.access(path, os.X_OK):
            return False, f"File is not executable: {executable_path}"

        # Check writability (security risk)
        if check_writability:
            is_writable, reason = is_user_writable(path)
            if is_writable:
                return False, (
                    f"Executable is in a user-writable location: {path}\n"
                    f"Reason: {reason}\n"
                    f"This is a security risk - use system-installed executables instead."
                )

        return True, None

    except (OSError, PermissionError) as e:
        return False, f"Error validating executable: {e}"


def find_executable_in_path(name: str) -> str | None:
    """
    Find an executable by name in the system PATH.

    Args:
        name: Executable name (e.g., "caddy", "python3")

    Returns:
        Absolute path to executable if found, None otherwise

    Examples:
        >>> find_executable_in_path("python3")
        '/usr/bin/python3'

        >>> find_executable_in_path("nonexistent")
        None
    """
    # Get PATH environment variable
    path_env = os.environ.get("PATH", "")
    path_dirs = path_env.split(os.pathsep)

    # On Windows, add .exe extension if not present
    if sys.platform == "win32" and not name.lower().endswith(".exe"):
        name = f"{name}.exe"

    # Search each directory in PATH
    for path_dir in path_dirs:
        candidate = Path(path_dir) / name
        if candidate.exists() and candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())

    return None


def validate_caddy_executable(caddy_path: str) -> tuple[bool, str | None]:
    """
    Validate Caddy executable with additional checks.

    Args:
        caddy_path: Path to Caddy executable

    Returns:
        (is_valid, error_message)
    """
    # First, run standard validation
    is_valid, error = validate_executable(caddy_path)
    if not is_valid:
        return is_valid, error

    # Additional check: try to get Caddy version
    import subprocess

    try:
        result = subprocess.run([caddy_path, "version"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False, f"Caddy executable failed version check: {result.stderr}"

        # Check that output contains "caddy"
        if "caddy" not in result.stdout.lower():
            return False, f"Executable does not appear to be Caddy: {result.stdout}"

    except subprocess.TimeoutExpired:
        return False, "Caddy version check timed out"
    except Exception as e:
        return False, f"Error checking Caddy version: {e}"

    return True, None
