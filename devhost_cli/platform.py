"""Platform detection and cross-platform utilities"""

import os
import platform
import shutil
import subprocess
import sys

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


def is_admin() -> bool:
    """Check if running with administrator/root privileges"""
    if not IS_WINDOWS:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _ps_quote(value: str) -> str:
    """Quote value for PowerShell"""
    return value.replace("`", "``").replace('"', '`"')


def relaunch_as_admin(args: list[str]) -> None:
    """Relaunch script with administrator privileges (Windows only)"""
    if not IS_WINDOWS:
        return
    python_exe = sys.executable
    from pathlib import Path

    script_dir = Path(__file__).parent.parent.resolve()
    script = str(script_dir / "devhost")
    launch_args = [script, "--elevated"] + args
    quoted_args = ",".join(f'"{_ps_quote(a)}"' for a in launch_args)
    ps_cmd = f'Start-Process -FilePath "{_ps_quote(python_exe)}" -ArgumentList @({quoted_args}) -Verb RunAs'
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=False)


def find_python() -> str | None:
    """Find Python executable, preferring venv"""
    from pathlib import Path

    script_dir = Path(__file__).parent.parent.resolve()
    router_dir = script_dir / "router"

    # Check for venv python
    candidates = [
        router_dir / "venv" / "bin" / "python",
        router_dir / "venv" / "Scripts" / "python.exe",
        router_dir / ".venv" / "bin" / "python",
        router_dir / ".venv" / "Scripts" / "python.exe",
        script_dir / ".venv" / "bin" / "python",
        script_dir / ".venv" / "Scripts" / "python.exe",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return str(candidate)

    # Fallback to system python
    return shutil.which("python3") or shutil.which("python")
