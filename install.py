#!/usr/bin/env python3
"""Devhost standalone installer (Linux/macOS/Windows)."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent
ROUTER_DIR = ROOT_DIR / "router"
DOMAIN_FILE = ROOT_DIR / ".devhost" / "domain"
CONFIG_FILE = ROOT_DIR / "devhost.json"
CADDYFILE = ROOT_DIR / "caddy" / "Caddyfile"
CADDY_TEMPLATE = ROOT_DIR / "caddy" / "Caddyfile.template"

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


class Colors:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"

    @classmethod
    def disable(cls) -> None:
        cls.RESET = cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = ""


def _enable_colors() -> None:
    if os.environ.get("NO_COLOR"):
        Colors.disable()
        return
    if not sys.stdout.isatty():
        Colors.disable()
        return
    if IS_WINDOWS:
        try:
            os.system("")
        except Exception:
            pass


_enable_colors()


def msg_ok(text: str) -> None:
    print(f"{Colors.GREEN}[+] {text}{Colors.RESET}")


def msg_warn(text: str) -> None:
    print(f"{Colors.YELLOW}[!] {text}{Colors.RESET}")


def msg_info(text: str) -> None:
    print(f"{Colors.BLUE}[*] {text}{Colors.RESET}")


def msg_error(text: str) -> None:
    print(f"{Colors.RED}[x] {text}{Colors.RESET}", file=sys.stderr)


def is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def run(cmd, check=False, capture=False, sudo=False, input_text: Optional[str] = None):
    if sudo and not IS_WINDOWS and not is_root():
        if shutil.which("sudo"):
            cmd = ["sudo"] + cmd
        else:
            msg_warn("sudo not found; cannot run privileged command.")
            return subprocess.CompletedProcess(cmd, 1, "", "")
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
        input=input_text,
    )


def prompt_yes_no(question: str, default: bool, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    suffix = "[Y/n]" if default else "[y/N]"
    reply = input(f"{question} {suffix} ").strip().lower()
    if not reply:
        return default
    return reply in {"y", "yes"}


def resolve_domain(domain_arg: Optional[str]) -> str:
    if domain_arg:
        return domain_arg.strip()
    env = os.environ.get("DEVHOST_DOMAIN")
    if env:
        return env.strip()
    if DOMAIN_FILE.exists():
        return DOMAIN_FILE.read_text(encoding="utf-8").strip() or "localhost"
    return "localhost"


def ensure_domain_file(domain: str) -> None:
    DOMAIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    DOMAIN_FILE.write_text(domain, encoding="utf-8")


def ensure_config_files() -> None:
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text("{}", encoding="utf-8")
    if not CADDYFILE.exists() and CADDY_TEMPLATE.exists():
        CADDYFILE.parent.mkdir(parents=True, exist_ok=True)
        CADDYFILE.write_text(CADDY_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")


# -------------------------- Linux Installer --------------------------

def _port_53_in_use() -> bool:
    if not shutil.which("ss"):
        return False
    result = run(["ss", "-lntup"], capture=True)
    return bool(re.search(r"[:.]53\s", result.stdout))


def linux_install(domain: str, assume_yes: bool) -> int:
    msg_info("Installing dependencies...")

    if shutil.which("caddy") is None:
        msg_info("Installing Caddy...")
        if not shutil.which("apt-get"):
            msg_warn("apt-get not found. Install Caddy manually: https://caddyserver.com/docs/install")
        else:
            run(["apt-get", "update"], sudo=True)
            run([
                "apt-get",
                "install",
                "-y",
                "debian-keyring",
                "debian-archive-keyring",
                "apt-transport-https",
                "curl",
                "gnupg",
            ], sudo=True)
            run([
                "bash",
                "-c",
                "curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg",
            ], sudo=True)
            run([
                "bash",
                "-c",
                "curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null",
            ], sudo=True)
            run(["apt-get", "update"], sudo=True)
            run(["apt-get", "install", "-y", "caddy"], sudo=True)

    msg_info("Setting up router venv...")
    python = shutil.which("python3")
    if not python:
        msg_error("python3 not found.")
        return 1
    run([python, "-m", "venv", str(ROUTER_DIR / "venv")])
    venv_py = ROUTER_DIR / "venv" / "bin" / "python"
    run([str(venv_py), "-m", "pip", "install", "-r", str(ROUTER_DIR / "requirements.txt")])

    if shutil.which("dnsmasq") is None:
        msg_info("Installing dnsmasq...")
        if shutil.which("apt-get"):
            run(["apt-get", "install", "-y", "dnsmasq"], sudo=True)
        else:
            msg_warn("apt-get not found. Install dnsmasq manually.")

    msg_info("Configuring dnsmasq...")
    dnsmasq_conf_dir = Path("/etc/dnsmasq.d")
    dnsmasq_conf_file = dnsmasq_conf_dir / "devhost.conf"
    dns_port = 53
    if _port_53_in_use():
        msg_warn("Port 53 is in use. Configuring dnsmasq on 127.0.0.1:5353.")
        dns_port = 5353
    content = (
        f"address=/{domain}/127.0.0.1\n"
        f"listen-address=127.0.0.1\n"
        "bind-interfaces\n"
        f"port={dns_port}\n"
    )

    if dnsmasq_conf_dir.exists():
        run(["tee", str(dnsmasq_conf_file)], sudo=True, input_text=content)
    else:
        dnsmasq_conf = Path("/etc/dnsmasq.conf")
        existing = ""
        try:
            if dnsmasq_conf.exists():
                existing = dnsmasq_conf.read_text()
        except Exception:
            existing = ""
        if f"address=/{domain}/127.0.0.1" not in existing:
            run(["bash", "-c", f"echo 'address=/{domain}/127.0.0.1' >> {dnsmasq_conf}"], sudo=True)
        if "listen-address=127.0.0.1" not in existing:
            run(["bash", "-c", "echo 'listen-address=127.0.0.1' >> /etc/dnsmasq.conf"], sudo=True)
        if "bind-interfaces" not in existing:
            run(["bash", "-c", "echo 'bind-interfaces' >> /etc/dnsmasq.conf"], sudo=True)
        if "port=" not in existing:
            run(["bash", "-c", f"echo 'port={dns_port}' >> /etc/dnsmasq.conf"], sudo=True)

    if shutil.which("systemctl"):
        run(["systemctl", "restart", "dnsmasq"], sudo=True)

    if dns_port != 53:
        if shutil.which("systemctl"):
            resolved = run(["systemctl", "is-active", "systemd-resolved"], capture=True)
            if resolved.returncode == 0:
                msg_info(f"Configuring systemd-resolved for *.{domain} -> 127.0.0.1#{dns_port}")
                resolved_dropin_dir = Path("/etc/systemd/resolved.conf.d")
                resolved_file = resolved_dropin_dir / "devhost.conf"
                resolved_content = f"[Resolve]\nDNS=127.0.0.1#{dns_port}\nDomains=~{domain}\n"
                run(["mkdir", "-p", str(resolved_dropin_dir)], sudo=True)
                run(["tee", str(resolved_file)], sudo=True, input_text=resolved_content)
                run(["systemctl", "restart", "systemd-resolved"], sudo=True)
            else:
                msg_warn("systemd-resolved not active; configure resolver manually.")

    msg_warn("About to update DNS resolver configuration. Review /etc/resolv.conf if needed.")
    msg_info("If using systemd-resolved, run:")
    print("  sudo ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf")

    msg_info("Installing devhost CLI...")
    run(["chmod", "+x", str(ROOT_DIR / "devhost")])
    run(["ln", "-sf", str(ROOT_DIR / "devhost"), "/usr/local/bin/devhost"], sudo=True)

    ensure_config_files()
    ensure_domain_file(domain)

    msg_ok("Done! You can now run 'devhost add <name> <port>'")
    return 0


# -------------------------- macOS Installer --------------------------

def detect_uvicorn() -> Optional[str]:
    candidates = [
        ROOT_DIR / ".venv" / "bin" / "uvicorn",
        ROUTER_DIR / ".venv" / "bin" / "uvicorn",
        ROUTER_DIR / "venv" / "bin" / "uvicorn",
        Path("/usr/local/bin/uvicorn"),
        Path("/opt/homebrew/bin/uvicorn"),
    ]
    for c in candidates:
        if c.exists() and os.access(c, os.X_OK):
            return str(c)
    return shutil.which("uvicorn")


def generate_plist(template_path: Path, dest_path: Path, user: str, uvicorn_bin: str, uvicorn_args: Optional[list[str]]) -> None:
    text = template_path.read_text(encoding="utf-8")
    text = text.replace("{{USER}}", user)
    text = text.replace("{{UVICORN_BIN}}", uvicorn_bin)
    if uvicorn_args:
        args_text = "\n".join([f"    <string>{arg}</string>" for arg in uvicorn_args])
        text = text.replace("{{UVICORN_ARGS}}", args_text)
    else:
        text = text.replace("{{UVICORN_ARGS}}\n", "")
        text = text.replace("{{UVICORN_ARGS}}", "")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(text, encoding="utf-8")


def macos_install(domain: str, args) -> int:
    template = ROOT_DIR / "router" / "devhost-router.plist.tmpl"
    dest = Path.home() / "Library" / "LaunchAgents" / "devhost.router.plist"

    if not template.exists():
        msg_error(f"Template not found: {template}")
        return 1

    target_user = args.user or os.environ.get("USER", "")
    if not args.yes:
        resp = input(f"Enter target macOS username (press Enter to accept '{target_user}'): ").strip()
        if resp:
            target_user = resp

    uvicorn_path = args.uvicorn or detect_uvicorn()
    if uvicorn_path:
        msg_info(f"Found uvicorn at: {uvicorn_path}")
        if not args.yes:
            use = input("Use this uvicorn binary? [Y/n] ").strip().lower() or "y"
            if use not in {"y", "yes"}:
                uvicorn_path = None
    if not uvicorn_path:
        if args.yes:
            uvicorn_path = "python3 -m uvicorn"
        else:
            uvicorn_path = input("Enter full path to uvicorn (or leave empty to use 'python3 -m uvicorn'): ").strip()
            if not uvicorn_path:
                uvicorn_path = "python3 -m uvicorn"

    uvicorn_bin = ""
    uvicorn_args = None
    if " " in uvicorn_path:
        if uvicorn_path.strip() == "python3 -m uvicorn":
            python3 = shutil.which("python3")
            if not python3:
                msg_error("python3 not found; provide a full path to uvicorn.")
                return 1
            uvicorn_bin = python3
            uvicorn_args = ["-m", "uvicorn"]
        else:
            msg_error("Unsupported uvicorn command. Use a uvicorn binary path or 'python3 -m uvicorn'.")
            return 1
    else:
        uvicorn_bin = uvicorn_path
        if not (uvicorn_bin and os.path.exists(uvicorn_bin) and os.access(uvicorn_bin, os.X_OK)):
            msg_error(f"uvicorn binary not executable: {uvicorn_bin}")
            return 1

    msg_info("Summary of actions:")
    print(f" - Write LaunchAgent: {dest}")
    print(f" - Ensure resolver: /etc/resolver/{domain}")
    if args.start_dns:
        print(" - Start dnsmasq via Homebrew")
    if args.install_completions:
        print(" - Install shell completions")

    if not args.yes:
        if not prompt_yes_no("Proceed?", False, args.yes):
            print("Aborted.")
            return 0

    if args.dry_run:
        msg_info("Dry run complete.")
        return 0

    ensure_domain_file(domain)
    ensure_config_files()

    if dest.exists():
        backup = dest.with_suffix(f".plist.{int(time.time())}.bak")
        shutil.copy2(dest, backup)

    generate_plist(template, dest, target_user, uvicorn_bin, uvicorn_args)
    msg_ok(f"LaunchAgent installed: {dest}")

    resolver_dir = Path("/etc/resolver")
    resolver_file = resolver_dir / domain
    run(["mkdir", "-p", str(resolver_dir)], sudo=True)
    run(["tee", str(resolver_file)], sudo=True, input_text="nameserver 127.0.0.1\n")

    start_dns = args.start_dns
    if not args.yes and not start_dns:
        start_dns = prompt_yes_no("Start dnsmasq via Homebrew services now?", False, args.yes)
    if start_dns:
        if shutil.which("brew"):
            run(["brew", "services", "start", "dnsmasq"], check=False)
        else:
            msg_warn("brew not found; install dnsmasq manually.")

    install_completions = args.install_completions
    if not args.yes and not install_completions:
        install_completions = prompt_yes_no("Install shell completions?", False, args.yes)
    if install_completions:
        zsh_dir = Path.home() / ".zsh" / "completions"
        bash_dir = Path.home() / ".bash_completion.d"
        zsh_dir.mkdir(parents=True, exist_ok=True)
        bash_dir.mkdir(parents=True, exist_ok=True)
        if (ROOT_DIR / "completions" / "_devhost").exists():
            shutil.copy2(ROOT_DIR / "completions" / "_devhost", zsh_dir / "_devhost")
            msg_ok(f"Installed zsh completion to {zsh_dir / '_devhost'}")
        if (ROOT_DIR / "completions" / "devhost.bash").exists():
            shutil.copy2(ROOT_DIR / "completions" / "devhost.bash", bash_dir / "devhost")
            msg_ok(f"Installed bash completion to {bash_dir / 'devhost'}")

    run(["launchctl", "unload", str(dest)], check=False)
    run(["launchctl", "load", "-w", str(dest)], check=False)

    msg_ok("Setup complete. Check router health with: curl http://127.0.0.1:5555/health")
    msg_info("Logs: tail -f /tmp/devhost-router.log /tmp/devhost-router.err")
    return 0


# -------------------------- Windows Installer --------------------------

def find_python_windows() -> Optional[str]:
    if shutil.which("py"):
        result = run(["py", "-3", "-c", "import sys; print(sys.executable)"], capture=True)
        if result.stdout.strip():
            return result.stdout.strip()
    if shutil.which("python"):
        result = run(["python", "-c", "import sys; print(sys.executable)"], capture=True)
        if result.stdout.strip():
            return result.stdout.strip()
    return None


def find_caddy_exe() -> Optional[str]:
    cmd = shutil.which("caddy")
    if cmd:
        return cmd
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if base.exists():
        for path in base.glob("CaddyServer.Caddy*\\caddy.exe"):
            return str(path)
    return None


def windows_clean(assume_yes: bool) -> bool:
    if not prompt_yes_no("This will remove venv, devhost.json, caddy/Caddyfile, and .devhost. Continue?", False, assume_yes):
        return False
    pid_file = ROOT_DIR / ".devhost" / "router.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            run(["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"], check=False)
        except Exception:
            pass
        pid_file.unlink(missing_ok=True)

    run(["powershell", "-NoProfile", "-Command", "Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"], check=False)

    venv_dir = ROUTER_DIR / "venv"
    if venv_dir.exists():
        try:
            shutil.rmtree(venv_dir)
        except Exception:
            msg_warn("Failed to remove venv folder. Close any Python/uvicorn processes and retry.")
            return False

    for path in [CONFIG_FILE, CADDYFILE]:
        if path.exists():
            path.unlink()
    devhost_dir = ROOT_DIR / ".devhost"
    if devhost_dir.exists():
        shutil.rmtree(devhost_dir, ignore_errors=True)

    msg_ok("Clean complete.")
    return True


def windows_install(domain: str, args) -> int:
    if args.clean:
        if not windows_clean(args.yes):
            return 1

    python = find_python_windows() or sys.executable
    if not python:
        msg_error("Python not found. Install Python 3.x and retry.")
        return 1

    venv_dir = ROUTER_DIR / "venv"
    venv_cfg = venv_dir / "pyvenv.cfg"
    if venv_dir.exists() and not venv_cfg.exists():
        msg_warn("Existing venv missing pyvenv.cfg. Recreating...")
        shutil.rmtree(venv_dir, ignore_errors=True)

    if venv_cfg.exists():
        for line in venv_cfg.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("home = "):
                home = line.replace("home = ", "").strip()
                if not re.match(r"^[A-Za-z]:\\", home):
                    msg_warn(f"Existing venv points to non-Windows python ({home}). Recreating...")
                    shutil.rmtree(venv_dir, ignore_errors=True)
                    break

    msg_info(f"Creating venv at {venv_dir}")
    run([python, "-m", "venv", str(venv_dir)])
    if not venv_cfg.exists():
        msg_error(f"pyvenv.cfg not found after venv creation at {venv_dir}.")
        return 1

    venv_py = venv_dir / "Scripts" / "python.exe"
    if not venv_py.exists():
        msg_error(f"Venv python not found at {venv_py}")
        return 1

    msg_info("Installing router requirements")
    run([str(venv_py), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(venv_py), "-m", "pip", "install", "-r", str(ROUTER_DIR / "requirements.txt")])

    ensure_config_files()
    ensure_domain_file(domain)

    if args.caddy:
        msg_info("Installing Caddy (if needed)")
        if not find_caddy_exe():
            if shutil.which("winget"):
                run(["winget", "install", "-e", "--id", "CaddyServer.Caddy"], check=False)
                if not find_caddy_exe():
                    run(["winget", "install", "-e", "--id", "Caddy.Caddy"], check=False)
            elif shutil.which("scoop"):
                run(["scoop", "install", "caddy"], check=False)
            elif shutil.which("choco"):
                run(["choco", "install", "caddy", "-y"], check=False)
            else:
                msg_warn("No package manager found. Install Caddy manually: https://caddyserver.com/docs/install")

    port80 = run([
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-NetTCPConnection -LocalPort 80 -ErrorAction SilentlyContinue | Select-Object -First 1 | ConvertTo-Json",
    ], capture=True)
    if port80.stdout.strip():
        try:
            data = json.loads(port80.stdout)
            pid = int(data.get("OwningProcess"))
            proc_name = run([
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue).ProcessName",
            ], capture=True)
            name = proc_name.stdout.strip() or "unknown"
            msg_warn(f"Port 80 is in use by {name} (pid {pid}).")
            if name.lower() == "wslrelay" and shutil.which("wsl"):
                if prompt_yes_no("Shutdown WSL now to free port 80?", True, args.yes):
                    run(["wsl", "--shutdown"], check=False)
                    msg_ok("WSL shut down.")
            else:
                if prompt_yes_no(f"Stop {name} (pid {pid}) to free port 80?", False, args.yes):
                    if name.lower() == "caddy":
                        exe = find_caddy_exe()
                        if exe:
                            run([exe, "stop"], check=False)
                        else:
                            run([
                                "powershell",
                                "-NoProfile",
                                "-Command",
                                f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue",
                            ], check=False)
                    else:
                        run([
                            "powershell",
                            "-NoProfile",
                            "-Command",
                            f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue",
                        ], check=False)
        except Exception:
            pass

    msg_info("Next steps:")
    print("1) Start both Caddy + router:")
    print("   python .\\devhost start")
    print("   # or")
    print("   .\\devhost.ps1 start")
    print("2) Add a mapping:")
    print("   python .\\devhost add hello 8000")
    print("   # or")
    print("   .\\devhost.ps1 add hello 8000")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Devhost installer")
    parser.add_argument("--windows", action="store_true")
    parser.add_argument("--macos", action="store_true")
    parser.add_argument("--linux", action="store_true")
    parser.add_argument("--domain", help="Base domain to use")
    parser.add_argument("--yes", "-y", action="store_true", help="Assume yes for prompts")
    parser.add_argument("--dry-run", action="store_true", help="macOS: show actions without changes")
    parser.add_argument("--start-dns", action="store_true", help="macOS: start dnsmasq via Homebrew")
    parser.add_argument("--install-completions", action="store_true", help="macOS: install shell completions")
    parser.add_argument("--uvicorn", help="macOS: uvicorn path or 'python3 -m uvicorn'")
    parser.add_argument("--user", help="macOS: target username")
    parser.add_argument("--caddy", action="store_true", help="Windows: install Caddy")
    parser.add_argument("--clean", action="store_true", help="Windows: remove venv/configs")
    args = parser.parse_args()

    domain = resolve_domain(args.domain)

    if args.windows or (IS_WINDOWS and not (args.macos or args.linux)):
        return windows_install(domain, args)
    if args.macos or (IS_MACOS and not (args.windows or args.linux)):
        return macos_install(domain, args)
    if args.linux or (IS_LINUX and not (args.windows or args.macos)):
        return linux_install(domain, args.yes)

    msg_error("Unsupported platform.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
