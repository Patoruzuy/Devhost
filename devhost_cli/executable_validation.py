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
import stat
import sys
from pathlib import Path
from typing import Optional, Tuple

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
    "/usr/local/opt",     # Homebrew traditional
    # Windows system paths
    r"C:\Windows\System32",
    r"C:\Windows\SysWOW64",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
}


def is_user_writable(path: Path) -> bool:
    """
    Check if a path is in a user-writable location.
    
    Returns True if the path is potentially unsafe (user can modify it).
    Returns False if the path is in a system-controlled location.
    
    Args:
        path: Path to check
        
    Returns:
        True if user-writable (unsafe), False if system-controlled (safe)
    """
    try:
        path_str = str(path.resolve())
        
        # Check if in a known safe directory
        for safe_dir in SAFE_EXECUTABLE_DIRS:
            if path_str.startswith(safe_dir):
                return False
        
        # On Unix systems, check actual file permissions
        if sys.platform != "win32":
            path_stat = path.stat()
            # If world-writable or group-writable, consider unsafe
            mode = path_stat.st_mode
            if mode & stat.S_IWOTH:  # World-writable
                return True
            if mode & stat.S_IWGRP:  # Group-writable
                return True
            
            # If owned by current user and in home directory, consider user-writable
            if path_stat.st_uid == os.getuid() and str(path).startswith(str(Path.home())):
                return True
        
        # On Windows, check if in user profile directory
        if sys.platform == "win32":
            userprofile = os.environ.get("USERPROFILE", "")
            if userprofile and path_str.startswith(userprofile):
                return True
        
        # Default to safe if we can't determine
        return False
        
    except (OSError, PermissionError):
        # If we can't stat the file, assume it's unsafe
        return True


def validate_executable(
    executable_path: str,
    check_writability: bool = True
) -> Tuple[bool, Optional[str]]:
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
        # Resolve to absolute path
        path = Path(executable_path).resolve()
        
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
        if check_writability and is_user_writable(path):
            return False, (
                f"Executable is in a user-writable location: {path}\n"
                f"This is a security risk - use system-installed executables instead."
            )
        
        return True, None
        
    except (OSError, PermissionError) as e:
        return False, f"Error validating executable: {e}"


def find_executable_in_path(name: str) -> Optional[str]:
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


def validate_caddy_executable(caddy_path: str) -> Tuple[bool, Optional[str]]:
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
        result = subprocess.run(
            [caddy_path, "version"],
            capture_output=True,
            text=True,
            timeout=5
        )
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
