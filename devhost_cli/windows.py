"""Windows-specific utilities (hosts file, Caddy management)"""

import json
import os
import subprocess
import time
from pathlib import Path

from .config import Config
from .platform import IS_WINDOWS
from .utils import msg_error, msg_info, msg_success, msg_warning


def hosts_path() -> Path:
    """Get Windows hosts file path"""
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    return Path(system_root) / "System32" / "drivers" / "etc" / "hosts"


def hosts_add(hostname: str) -> None:
    """Add hostname to Windows hosts file"""
    if not hostname:
        return
    path = hosts_path()
    if not path.exists():
        return
    content = path.read_text(encoding="ascii", errors="ignore")
    if any(
        line.strip().startswith("127.0.0.1") and hostname in line and "devhost" in line for line in content.splitlines()
    ):
        return
    with path.open("a", encoding="ascii") as fh:
        fh.write(f"\n127.0.0.1 {hostname} # devhost")


def hosts_remove(hostname: str) -> None:
    """Remove hostname from Windows hosts file"""
    if not hostname:
        return
    path = hosts_path()
    if not path.exists():
        return
    lines = path.read_text(encoding="ascii", errors="ignore").splitlines()
    filtered = [line for line in lines if not (hostname in line and "devhost" in line)]
    path.write_text("\n".join(filtered) + ("\n" if filtered else ""), encoding="ascii")


def hosts_sync() -> None:
    """Sync all mappings to Windows hosts file"""
    domain = Config().get_domain()
    if domain == "localhost":
        return
    cfg = Config().load()
    for name in cfg.keys():
        hosts_add(f"{name}.{domain}")
    msg_success("Hosts entries synced.")


def hosts_clear() -> None:
    """Clear all devhost entries from Windows hosts file"""
    path = hosts_path()
    if not path.exists():
        msg_warning("Hosts file not found.")
        return
    lines = path.read_text(encoding="ascii", errors="ignore").splitlines()
    filtered = [line for line in lines if "devhost" not in line]
    path.write_text("\n".join(filtered) + ("\n" if filtered else ""), encoding="ascii")
    msg_success("Hosts entries cleared.")


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

        req = urllib.request.Request("http://127.0.0.1:5555/health")
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
