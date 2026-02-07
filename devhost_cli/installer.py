#!/usr/bin/env python3
"""Devhost installer entrypoint.

This helper performs opt-in setup actions such as installing Caddy and
shell completions. It avoids implicit privileged changes and always
requires explicit confirmation unless --yes is provided.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from devhost_cli.config import Config
from devhost_cli.platform import IS_WINDOWS
from devhost_cli.utils import msg_error, msg_info, msg_success, msg_warning


def _confirm(action: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    msg_warning(f"About to: {action}")
    try:
        response = input("Continue? [y/N]: ").strip().lower()
        return response in {"y", "yes"}
    except (EOFError, KeyboardInterrupt):
        msg_info("\nOperation cancelled by user")
        return False


def _run_cmd(cmd: list[str], dry_run: bool, assume_yes: bool) -> bool:
    msg_info("Running: " + " ".join(cmd))
    if dry_run:
        return True
    if not _confirm("run command", assume_yes):
        return False
    result = subprocess.run(cmd, check=False)
    return result.returncode == 0


def _install_completions(dry_run: bool) -> bool:
    root = Path(__file__).parent.parent.resolve()
    src_zsh = root / "completions" / "_devhost"
    src_bash = root / "completions" / "devhost.bash"
    ok = True

    if src_zsh.exists() and not IS_WINDOWS:
        dest_dir = Path.home() / ".zsh" / "completions"
        dest = dest_dir / "_devhost"
        msg_info(f"Installing zsh completions to {dest}")
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_zsh, dest)
    elif IS_WINDOWS:
        msg_warning("Skipping zsh completions on Windows.")

    if src_bash.exists() and not IS_WINDOWS:
        dest_dir = Path.home() / ".bash_completion.d"
        dest = dest_dir / "devhost"
        msg_info(f"Installing bash completions to {dest}")
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_bash, dest)
    elif IS_WINDOWS:
        msg_warning("Skipping bash completions on Windows.")

    msg_info("Shell setup (if needed):")
    msg_info("  Zsh:  fpath=(~/.zsh/completions $fpath); autoload -U compinit && compinit")
    msg_info("  Bash: source ~/.bash_completion.d/devhost")
    return ok


def _clean_completions(dry_run: bool) -> bool:
    paths = [
        Path.home() / ".zsh" / "completions" / "_devhost",
        Path.home() / ".bash_completion.d" / "devhost",
    ]
    for path in paths:
        if path.exists():
            msg_info(f"Removing {path}")
            if not dry_run:
                path.unlink(missing_ok=True)
    return True


def _install_caddy(dry_run: bool, assume_yes: bool) -> bool:
    if shutil.which("caddy"):
        msg_success("Caddy is already installed.")
        return True

    if IS_WINDOWS:
        if not shutil.which("winget"):
            msg_error("winget not found. Install Caddy manually from https://caddyserver.com/download")
            return False
        return _run_cmd(["winget", "install", "CaddyServer.Caddy"], dry_run, assume_yes)

    if sys.platform == "darwin":
        if not shutil.which("brew"):
            msg_error("Homebrew not found. Install from https://brew.sh then run: brew install caddy")
            return False
        return _run_cmd(["brew", "install", "caddy"], dry_run, assume_yes)

    # Linux / other Unix
    for manager, cmd in (
        ("apt-get", ["sudo", "apt-get", "install", "-y", "caddy"]),
        ("dnf", ["sudo", "dnf", "install", "-y", "caddy"]),
        ("yum", ["sudo", "yum", "install", "-y", "caddy"]),
        ("pacman", ["sudo", "pacman", "-S", "--noconfirm", "caddy"]),
    ):
        if shutil.which(manager):
            return _run_cmd(cmd, dry_run, assume_yes)

    msg_error("Unsupported package manager. Install Caddy manually from https://caddyserver.com/docs/install")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Devhost installer")
    parser.add_argument("--windows", action="store_true")
    parser.add_argument("--macos", action="store_true")
    parser.add_argument("--linux", action="store_true")
    parser.add_argument("--caddy", action="store_true", help="Install Caddy")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without running")
    parser.add_argument("--start-dns", action="store_true", help="(Info only) DNS setup guidance")
    parser.add_argument("--install-completions", action="store_true")
    parser.add_argument("--domain")
    parser.add_argument("--uvicorn")
    parser.add_argument("--user")
    parser.add_argument("--clean", action="store_true", help="Remove installer-managed artifacts")
    parser.add_argument("rest", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)

    if args.windows and not IS_WINDOWS:
        msg_error("--windows specified but this is not Windows.")
        return 1
    if args.macos and sys.platform != "darwin":
        msg_error("--macos specified but this is not macOS.")
        return 1
    if args.linux and sys.platform == "darwin":
        msg_error("--linux specified but this is macOS.")
        return 1

    success = True

    if args.clean:
        success = _clean_completions(args.dry_run) and success

    if args.domain:
        try:
            Config().set_domain(args.domain)
        except Exception as exc:
            msg_error(f"Failed to set domain: {exc}")
            success = False

    if args.install_completions:
        success = _install_completions(args.dry_run) and success

    if args.start_dns:
        msg_info("DNS setup is environment-specific. See docs/troubleshooting.md for options.")

    if args.caddy:
        success = _install_caddy(args.dry_run, args.yes) and success

    if args.uvicorn or args.user or args.rest:
        msg_warning("Some flags are not handled by the installer helper in this build.")

    if not any(
        [
            args.clean,
            args.domain,
            args.install_completions,
            args.start_dns,
            args.caddy,
        ]
    ):
        msg_info("No installer actions selected. Use --caddy or --install-completions.")

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
