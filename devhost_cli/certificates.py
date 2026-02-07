"""Certificate management and validation for Devhost

This module provides certificate security features including:
- Permission checks for private keys (0600 on Unix)
- Certificate expiration warnings (30-day threshold)
- Certificate verification configuration
- Storage location validation
"""

import logging
import os
import stat
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("devhost.certificates")


def check_key_permissions(key_path: Path) -> tuple[bool, str]:
    """Check if private key has secure permissions (0600 on Unix)

    Args:
        key_path: Path to private key file

    Returns:
        Tuple of (is_secure, error_message)
        - is_secure: True if permissions are secure or on Windows
        - error_message: Empty string if secure, error message otherwise
    """
    if not key_path.exists():
        return False, f"Key file does not exist: {key_path}"

    # Windows doesn't use Unix permissions - rely on NTFS ACLs
    if os.name == "nt":
        return True, ""

    # Unix: Check file permissions
    try:
        file_stat = key_path.stat()
        mode = file_stat.st_mode

        # Check if world-readable (S_IROTH) or world-writable (S_IWOTH)
        if mode & (stat.S_IROTH | stat.S_IWOTH):
            return False, f"Private key {key_path} is world-readable/writable (permissions: {oct(stat.S_IMODE(mode))})"

        # Check if group-readable (S_IRGRP) or group-writable (S_IWGRP)
        if mode & (stat.S_IRGRP | stat.S_IWGRP):
            logger.warning(
                f"Private key {key_path} is group-readable/writable (permissions: {oct(stat.S_IMODE(mode))}). Consider setting to 0600."
            )

        # Ideal: 0600 (owner read/write only)
        ideal_mode = stat.S_IRUSR | stat.S_IWUSR
        if stat.S_IMODE(mode) != ideal_mode:
            current_perms = oct(stat.S_IMODE(mode))
            logger.info(f"Private key {key_path} has permissions {current_perms}, recommended: 0600")

        return True, ""

    except (OSError, PermissionError) as e:
        return False, f"Cannot check permissions for {key_path}: {e}"


def set_secure_key_permissions(key_path: Path) -> tuple[bool, str]:
    """Set secure permissions (0600) on private key file (Unix only)

    Args:
        key_path: Path to private key file

    Returns:
        Tuple of (success, error_message)
    """
    if not key_path.exists():
        return False, f"Key file does not exist: {key_path}"

    # Windows doesn't use Unix permissions
    if os.name == "nt":
        return True, "Windows uses NTFS ACLs (skipping chmod)"

    try:
        # Set to 0600 (rw-------)
        key_path.chmod(0o600)
        logger.info(f"Set secure permissions (0600) on {key_path}")
        return True, ""
    except (OSError, PermissionError) as e:
        return False, f"Cannot set permissions on {key_path}: {e}"


def check_certificate_expiration(cert_path: Path, warning_days: int = 30) -> tuple[bool, datetime | None, str]:
    """Check if certificate is expiring soon

    Args:
        cert_path: Path to certificate file (.pem, .crt)
        warning_days: Number of days before expiration to warn (default: 30)

    Returns:
        Tuple of (is_expiring_soon, expiration_date, message)
        - is_expiring_soon: True if expires within warning_days
        - expiration_date: Certificate expiration date (None if cannot parse)
        - message: Human-readable status message
    """
    if not cert_path.exists():
        return False, None, f"Certificate file does not exist: {cert_path}"

    try:
        # Try importing cryptography if available
        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend

            with cert_path.open("rb") as f:
                cert_data = f.read()

            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            expiration_date = cert.not_valid_after_utc.replace(tzinfo=None)

            days_until_expiry = (expiration_date - datetime.now()).days

            if days_until_expiry < 0:
                return (
                    True,
                    expiration_date,
                    f"Certificate {cert_path.name} EXPIRED on {expiration_date.strftime('%Y-%m-%d')}",
                )
            elif days_until_expiry <= warning_days:
                return (
                    True,
                    expiration_date,
                    f"Certificate {cert_path.name} expires in {days_until_expiry} days ({expiration_date.strftime('%Y-%m-%d')})",
                )
            else:
                return (
                    False,
                    expiration_date,
                    f"Certificate {cert_path.name} valid until {expiration_date.strftime('%Y-%m-%d')} ({days_until_expiry} days remaining)",
                )

        except ImportError:
            # Fallback: Try using openssl command
            import subprocess

            result = subprocess.run(
                ["openssl", "x509", "-in", str(cert_path), "-noout", "-enddate"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                # Parse output: "notAfter=Feb  5 12:00:00 2027 GMT"
                enddate_line = result.stdout.strip()
                if enddate_line.startswith("notAfter="):
                    date_str = enddate_line.split("=", 1)[1]
                    # Parse various OpenSSL date formats
                    for fmt in ["%b %d %H:%M:%S %Y %Z", "%b  %d %H:%M:%S %Y %Z"]:
                        try:
                            expiration_date = datetime.strptime(date_str, fmt)
                            days_until_expiry = (expiration_date - datetime.now()).days

                            if days_until_expiry < 0:
                                return (
                                    True,
                                    expiration_date,
                                    f"Certificate {cert_path.name} EXPIRED on {expiration_date.strftime('%Y-%m-%d')}",
                                )
                            elif days_until_expiry <= warning_days:
                                return (
                                    True,
                                    expiration_date,
                                    f"Certificate {cert_path.name} expires in {days_until_expiry} days ({expiration_date.strftime('%Y-%m-%d')})",
                                )
                            else:
                                return (
                                    False,
                                    expiration_date,
                                    f"Certificate {cert_path.name} valid until {expiration_date.strftime('%Y-%m-%d')} ({days_until_expiry} days remaining)",
                                )
                        except ValueError:
                            continue

            # Cannot parse - not a critical error
            return (
                False,
                None,
                f"Cannot check expiration for {cert_path.name} (install cryptography package or openssl for full validation)",
            )

    except Exception as e:
        logger.debug(f"Certificate expiration check failed for {cert_path}: {e}")
        return False, None, f"Cannot check expiration for {cert_path.name}: {e}"


def get_cert_storage_locations() -> dict[str, Path]:
    """Get expected certificate storage locations

    Returns:
        Dictionary mapping location names to paths
    """
    locations = {}

    # User-specific Caddy certs (most common for devhost)
    caddy_user = Path.home() / ".local" / "share" / "caddy" / "certificates"
    if caddy_user.exists():
        locations["caddy_user"] = caddy_user

    # System Caddy certs
    if os.name != "nt":
        caddy_system = Path("/var/lib/caddy/.local/share/caddy/certificates")
        if caddy_system.exists():
            locations["caddy_system"] = caddy_system

    # User config directory
    devhost_certs = Path.home() / ".devhost" / "certificates"
    if devhost_certs.exists():
        locations["devhost_user"] = devhost_certs

    return locations


def validate_all_certificates(warning_days: int = 30) -> dict[str, list[str]]:
    """Validate all certificates in known storage locations

    Args:
        warning_days: Number of days before expiration to warn

    Returns:
        Dictionary with validation results:
        - 'warnings': List of warning messages
        - 'errors': List of error messages
        - 'info': List of info messages
    """
    results = {"warnings": [], "errors": [], "info": []}

    locations = get_cert_storage_locations()

    if not locations:
        results["info"].append("No certificate directories found")
        return results

    for location_name, location_path in locations.items():
        # Find all private keys
        for key_file in location_path.rglob("*.key"):
            is_secure, error_msg = check_key_permissions(key_file)
            if not is_secure:
                results["errors"].append(f"[{location_name}] {error_msg}")

        # Find all certificates
        for cert_file in location_path.rglob("*.pem"):
            if "key" in cert_file.name.lower():
                # Skip key files in .pem format
                continue

            is_expiring, exp_date, message = check_certificate_expiration(cert_file, warning_days)
            if is_expiring:
                if "EXPIRED" in message:
                    results["errors"].append(f"[{location_name}] {message}")
                else:
                    results["warnings"].append(f"[{location_name}] {message}")
            else:
                results["info"].append(f"[{location_name}] {message}")

    return results


def should_verify_certificates() -> bool:
    """Check if certificate verification should be enabled

    Returns DEVHOST_VERIFY_CERTS environment variable value (defaults to True)
    """
    verify = os.environ.get("DEVHOST_VERIFY_CERTS", "1")
    return verify.lower() in ("1", "true", "yes", "on")


def log_certificate_status() -> None:
    """Log certificate status on startup (for monitoring)"""
    try:
        results = validate_all_certificates()

        if results["errors"]:
            for error in results["errors"]:
                logger.error(error)

        if results["warnings"]:
            for warning in results["warnings"]:
                logger.warning(warning)

        # Only log info in debug mode
        if logger.isEnabledFor(logging.DEBUG):
            for info in results["info"]:
                logger.debug(info)

    except Exception as e:
        logger.debug(f"Certificate validation failed: {e}")
