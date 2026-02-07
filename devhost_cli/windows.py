"""Windows-specific utilities (hosts file, Caddy management)"""

import ctypes
import json
import logging
import os
import subprocess
import time
from pathlib import Path

from .config import Config
from .platform import IS_WINDOWS
from .utils import msg_error, msg_info, msg_success, msg_warning

logger = logging.getLogger("devhost.windows")

logger = logging.getLogger("devhost.windows")


def is_admin() -> bool:
    """Check if current process has administrator privileges on Windows."""
    if not IS_WINDOWS:
        return False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def confirm_action(action: str, target: str) -> bool:
    """Prompt user to confirm privileged action.

    Args:
        action: Action description (e.g., "modify hosts file")
        target: Target of action (e.g., hostname)

    Returns:
        True if user confirms, False otherwise
    """
    msg_warning(f"About to {action}: {target}")
    msg_info("This requires administrator privileges and will modify system files.")

    try:
        response = input("Continue? [y/N]: ").strip().lower()
        return response in {"y", "yes"}
    except (EOFError, KeyboardInterrupt):
        msg_info("\nOperation cancelled by user")
        return False


def hosts_path() -> Path:
    """Get Windows hosts file path"""
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    return Path(system_root) / "System32" / "drivers" / "etc" / "hosts"


def hosts_backup() -> Path | None:
    """Create a backup of the hosts file before modification.

    Returns the backup path if successful, None otherwise.
    Prevents catastrophic networking issues from hosts file corruption.
    """
    path = hosts_path()
    if not path.exists():
        return None
    backup_path = path.with_suffix(".bak")
    try:
        content = path.read_text(encoding="ascii", errors="ignore")
        backup_path.write_text(content, encoding="ascii")
        return backup_path
    except PermissionError:
        # Running without admin - can't backup, but that also means can't modify
        return None
    except Exception:
        return None


def hosts_restore(confirm: bool = True) -> bool:
    """Restore hosts file from backup.

    Security:
        - Requires admin privileges
        - Optional confirmation gate

    Returns True if restore was successful.
    """
    if not is_admin():
        msg_error("Administrator privileges required to restore hosts file")
        msg_info("Run in an elevated PowerShell/Command Prompt")
        logger.error("hosts_restore failed: not running as admin")
        return False

    path = hosts_path()
    backup_path = path.with_suffix(".bak")
    if not backup_path.exists():
        msg_error(f"No hosts backup found at {backup_path}")
        logger.error("hosts_restore failed: backup not found at %s", backup_path)
        return False

    if confirm and not confirm_action("restore hosts file from backup", str(backup_path)):
        logger.info("User cancelled hosts_restore from %s", backup_path)
        return False

    try:
        content = backup_path.read_text(encoding="ascii", errors="ignore")
        path.write_text(content, encoding="ascii")
        msg_success("Hosts file restored from backup")
        logger.info("Successfully restored hosts file from %s", backup_path)
        return True
    except Exception as exc:
        msg_error(f"Failed to restore hosts file: {exc}")
        logger.error("hosts_restore failed: %s", exc)
        return False


def hosts_add(hostname: str, confirm: bool = True) -> None:
    """Add hostname to Windows hosts file.

    Security:
        - Requires admin privileges
        - Validates hostname format
        - Creates backup before modification
        - Logs all operations
    """
    if not hostname:
        logger.warning("hosts_add called with empty hostname")
        return

    # Security: Validate hostname format
    try:
        from devhost_cli.router.security import validate_hostname

        valid, error_msg = validate_hostname(hostname)
        if not valid:
            msg_error(f"Invalid hostname: {error_msg}")
            logger.warning("Rejected invalid hostname for hosts file: %s", hostname)
            return
    except ImportError:
        # Fallback validation if security module unavailable
        if not all(c.isalnum() or c in ".-" for c in hostname):
            msg_error("Hostname contains invalid characters")
            logger.warning("Rejected hostname with invalid chars: %s", hostname)
            return

    # Security: Check admin privileges
    if not is_admin():
        msg_error("Administrator privileges required to modify hosts file")
        msg_info("Run in an elevated PowerShell/Command Prompt")
        logger.error("hosts_add failed: not running as admin")
        return

    # Security: Confirm action (unless --yes flag used)
    if confirm and not confirm_action("add hosts entry", hostname):
        logger.info("User cancelled hosts_add for: %s", hostname)
        return

    path = hosts_path()
    if not path.exists():
        msg_error(f"Hosts file not found: {path}")
        logger.error("Hosts file missing: %s", path)
        return

    try:
        content = path.read_text(encoding="ascii", errors="ignore")
    except Exception as e:
        msg_error(f"Failed to read hosts file: {e}")
        logger.error("Failed to read %s: %s", path, e)
        return

    # Check if already exists
    if any(
        line.strip().startswith("127.0.0.1") and hostname in line and "devhost" in line for line in content.splitlines()
    ):
        msg_info(f"Entry for {hostname} already exists")
        logger.debug("Hosts entry already exists: %s", hostname)
        return

    # Backup before modifying
    backup_path = hosts_backup()
    if backup_path:
        logger.info("Created hosts backup: %s", backup_path)
    else:
        msg_warning("Could not create backup (non-critical)")

    try:
        with path.open("a", encoding="ascii") as fh:
            fh.write(f"\n127.0.0.1 {hostname} # devhost\n")
        msg_success(f"Added {hostname} to hosts file")
        logger.info("Successfully added hosts entry: %s", hostname)
    except PermissionError:
        msg_error("Permission denied writing to hosts file")
        logger.error("Permission denied for %s", path)
    except Exception as e:
        msg_error(f"Failed to update hosts file: {e}")
        logger.error("Failed to write %s: %s", path, e)


def hosts_remove(hostname: str, confirm: bool = True) -> None:
    """Remove hostname from Windows hosts file.

    Security:
        - Requires admin privileges
        - Creates backup before modification
        - Logs all operations
    """
    if not hostname:
        logger.warning("hosts_remove called with empty hostname")
        return

    # Security: Check admin privileges
    if not is_admin():
        msg_error("Administrator privileges required to modify hosts file")
        msg_info("Run in an elevated PowerShell/Command Prompt")
        logger.error("hosts_remove failed: not running as admin")
        return

    # Security: Confirm action
    if confirm and not confirm_action("remove hosts entry", hostname):
        logger.info("User cancelled hosts_remove for: %s", hostname)
        return

    path = hosts_path()
    if not path.exists():
        msg_warning("Hosts file not found")
        logger.warning("Hosts file missing: %s", path)
        return

    # Backup before modifying
    backup_path = hosts_backup()
    if backup_path:
        logger.info("Created hosts backup: %s", backup_path)

    try:
        lines = path.read_text(encoding="ascii", errors="ignore").splitlines()
        original_count = len(lines)
        filtered = [line for line in lines if not (hostname in line and "devhost" in line)]

        if len(filtered) == original_count:
            msg_info(f"No entry found for {hostname}")
            logger.debug("No hosts entry to remove: %s", hostname)
            return

        path.write_text("\n".join(filtered) + ("\n" if filtered else ""), encoding="ascii")
        msg_success(f"Removed {hostname} from hosts file")
        logger.info("Successfully removed hosts entry: %s", hostname)
    except PermissionError:
        msg_error("Permission denied writing to hosts file")
        logger.error("Permission denied for %s", path)
    except Exception as e:
        msg_error(f"Failed to update hosts file: {e}")
        logger.error("Failed to modify %s: %s", path, e)


def hosts_sync(confirm: bool = True) -> None:
    """Sync all mappings to Windows hosts file.

    Security:
        - Requires admin privileges
        - Validates all hostnames before adding
        - Logs all operations
    """
    if not is_admin():
        msg_error("Administrator privileges required to sync hosts file")
        msg_info("Run in an elevated PowerShell/Command Prompt")
        logger.error("hosts_sync failed: not running as admin")
        return

    domain = Config().get_domain()
    if domain == "localhost":
        msg_info("Using localhost domain, no hosts sync needed")
        logger.debug("Skipping hosts sync for localhost domain")
        return

    cfg = Config().load()
    if not cfg:
        msg_info("No routes configured")
        return

    if confirm and not confirm_action("sync hosts file entries", f"{len(cfg)} entries for *.{domain}"):
        logger.info("User cancelled hosts_sync")
        return

    msg_info(f"Syncing {len(cfg)} entries to hosts file...")
    logger.info("Starting hosts sync for %d entries", len(cfg))

    success_count = 0
    for name in cfg.keys():
        hostname = f"{name}.{domain}"
        try:
            hosts_add(hostname, confirm=False)  # Bulk operation, no per-entry confirmation
            success_count += 1
        except Exception as e:
            msg_error(f"Failed to add {hostname}: {e}")
            logger.error("Failed to add %s: %s", hostname, e)

    msg_success(f"Synced {success_count}/{len(cfg)} hosts entries")
    logger.info("Hosts sync complete: %d/%d successful", success_count, len(cfg))


def hosts_clear(confirm: bool = True) -> None:
    """Clear all devhost entries from Windows hosts file.

    Security:
        - Requires admin privileges
        - Creates backup before modification
        - Logs all operations
    """
    if not is_admin():
        msg_error("Administrator privileges required to clear hosts file")
        msg_info("Run in an elevated PowerShell/Command Prompt")
        logger.error("hosts_clear failed: not running as admin")
        return

    # Security: Confirm action (dangerous operation)
    if confirm and not confirm_action("clear all devhost entries from hosts file", "ALL ENTRIES"):
        logger.info("User cancelled hosts_clear")
        return

    path = hosts_path()
    if not path.exists():
        msg_warning("Hosts file not found.")
        logger.warning("Hosts file missing: %s", path)
        return

    # Backup before modifying
    backup_path = hosts_backup()
    if backup_path:
        logger.info("Created hosts backup: %s", backup_path)

    try:
        lines = path.read_text(encoding="ascii", errors="ignore").splitlines()
        original_count = len(lines)
        filtered = [line for line in lines if "devhost" not in line]
        removed_count = original_count - len(filtered)

        if removed_count == 0:
            msg_info("No devhost entries found")
            logger.debug("No devhost entries to clear")
            return

        path.write_text("\n".join(filtered) + ("\n" if filtered else ""), encoding="ascii")
        msg_success(f"Cleared {removed_count} devhost entries")
        logger.info("Successfully cleared %d hosts entries", removed_count)
    except PermissionError:
        msg_error("Permission denied writing to hosts file")
        logger.error("Permission denied for %s", path)
    except Exception as e:
        msg_error(f"Failed to clear hosts file: {e}")
        logger.error("Failed to modify %s: %s", path, e)


def find_caddy_exe() -> str | None:
    """Find Caddy executable on Windows"""
    import shutil

    cmd = shutil.which("caddy")
    if cmd:
        return cmd
    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
        if base.exists():
            for path in base.glob("CaddyServer.Caddy*\\caddy.exe"):
                return str(path)
    return None


def port80_owner_windows() -> tuple[str | None, int | None]:
    """Get process name and PID using port 80 on Windows"""
    if not IS_WINDOWS:
        return (None, None)
    ps = "Get-NetTCPConnection -LocalPort 80 -ErrorAction SilentlyContinue | Select-Object -First 1 | ConvertTo-Json"
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
        check=False,
    )
    if not result.stdout.strip():
        return (None, None)
    try:
        data = json.loads(result.stdout)
        pid = int(data.get("OwningProcess"))
    except Exception:
        return (None, None)
    name = None
    ps_name = f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue).ProcessName"
    result2 = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_name],
        capture_output=True,
        text=True,
        check=False,
    )
    if result2.stdout.strip():
        name = result2.stdout.strip()
    return (name, pid)


def caddy_start() -> None:
    """Start Caddy on Windows"""
    from pathlib import Path

    from .caddy import generate_caddyfile

    exe = find_caddy_exe()
    if not exe:
        msg_error("Caddy not found. Install with: devhost install --caddy")
        return
    existing = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Process caddy -ErrorAction SilentlyContinue"],
        capture_output=True,
        text=True,
    )
    if existing.stdout.strip():
        msg_info("Caddy already running")
        return
    name, pid = port80_owner_windows()
    if name and name.lower() != "caddy":
        msg_error(f"Port 80 is already in use by {name} (pid {pid}).")
        if name.lower() == "wslrelay":
            msg_warning("Hint: run 'wsl --shutdown' to free port 80.")
        msg_warning("Stop that process or free port 80, then retry.")
        return

    # Use user config directory (works for both pip install and source install)
    user_caddy = Path.home() / ".config" / "caddy" / "Caddyfile"
    user_caddy.parent.mkdir(parents=True, exist_ok=True)

    # Generate Caddyfile if it doesn't exist or regenerate from current routes
    generate_caddyfile()

    if not user_caddy.exists():
        msg_error(f"Caddyfile not found at {user_caddy}")
        msg_info("Run 'devhost add <name> <port>' to create a route first")
        return

    subprocess.run([exe, "start", "--config", str(user_caddy)], check=False)
    msg_success(f"Caddy starting with config: {user_caddy}")


def caddy_stop() -> None:
    """Stop Caddy on Windows"""
    exe = find_caddy_exe()
    if not exe:
        msg_error("Caddy not found.")
        return
    subprocess.run([exe, "stop"], check=False)
    msg_success("Caddy stop requested")


def caddy_restart() -> None:
    """Restart Caddy on Windows"""
    caddy_stop()
    time.sleep(1)
    caddy_start()


def caddy_status() -> None:
    """Check Caddy status on Windows"""
    if not IS_WINDOWS:
        msg_info("Caddy status is available on Windows via `devhost caddy status`.")
        return
    existing = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Process caddy -ErrorAction SilentlyContinue"],
        capture_output=True,
        text=True,
        check=False,
    )
    if existing.stdout.strip():
        msg_success("Caddy: running")
    else:
        msg_warning("Caddy: not running")


def doctor_windows(fix: bool = False) -> None:
    """Run Windows-specific diagnostics"""
    import shutil

    from .platform import is_admin

    print("Devhost doctor (Windows)")
    exe = find_caddy_exe()
    if exe:
        msg_info(f"Caddy: {exe}")
    else:
        msg_warning("Caddy: not found")
    name, pid = port80_owner_windows()
    if name:
        msg_warning(f"Port 80: in use by {name} (pid {pid})")
    else:
        msg_success("Port 80: free")

    # Check router health

    try:
        import urllib.request

        req = urllib.request.Request("http://127.0.0.1:7777/health")
        with urllib.request.urlopen(req, timeout=2) as response:
            if response.status == 200:
                msg_success("Router: OK")
            else:
                msg_warning("Router: not responding")
    except Exception:
        msg_warning("Router: not responding")

    domain = Config().get_domain()
    if domain != "localhost":
        path = hosts_path()
        if path.exists():
            content = path.read_text(encoding="ascii", errors="ignore")
            missing = []
            for name in Config().load().keys():
                entry = f"{name}.{domain}"
                if entry not in content:
                    missing.append(entry)
            if missing:
                msg_warning(f"Hosts: missing entries for {', '.join(missing)}")
            else:
                msg_success("Hosts: OK")
        else:
            msg_warning("Hosts file not found.")

    if fix:
        if not is_admin():
            msg_error("⚠️  Administrator privileges required for automatic fixes.")
            msg_info("Please run 'devhost doctor --windows --fix' from an elevated PowerShell.")
            return
        if domain != "localhost":
            hosts_sync()
        if name and name.lower() == "wslrelay" and shutil.which("wsl"):
            msg_info("Port 80 is held by wslrelay; shutting down WSL...")
            subprocess.run(["wsl", "--shutdown"], check=False)
        if exe:
            script_dir = Path(__file__).parent.parent.resolve()
            caddyfile = script_dir / "caddy" / "Caddyfile"
            subprocess.run([exe, "start", "--config", str(caddyfile)], check=False)
            msg_success("Caddy: start requested")
        else:
            msg_warning("Caddy not found; run devhost install --caddy")
