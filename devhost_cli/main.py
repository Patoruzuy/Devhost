"""Main entry point for devhost CLI"""

import argparse
import subprocess
import sys
from pathlib import Path

from . import __version__
from .cli import DevhostCLI
from .config import YAML_AVAILABLE, Config
from .platform import IS_WINDOWS, is_admin, relaunch_as_admin
from .utils import msg_error, msg_info, msg_success, msg_warning
from .windows import caddy_restart, caddy_start, caddy_status, caddy_stop, doctor_windows, hosts_clear, hosts_sync


def handle_init(args) -> bool:
    """Handle devhost init command - create devhost.yml"""
    if not YAML_AVAILABLE:
        msg_error("pyyaml not installed. Run: pip install devhost[yaml]")
        return False

    cwd = Path.cwd()
    config_file = cwd / "devhost.yml"

    if config_file.exists() and not args.yes:
        response = input("devhost.yml already exists. Overwrite? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            msg_info("Cancelled.")
            return False

    # Get values from args or prompt
    name = args.name
    port = args.port
    domain = args.domain

    if not args.yes:
        # Interactive mode
        default_name = cwd.name.lower().replace(" ", "-")
        if not name:
            name = input(f"App name [{default_name}]: ").strip() or default_name
        if port is None:
            port_input = input("Port [auto]: ").strip()
            port = int(port_input) if port_input else 0
        if domain == "localhost":
            domain_input = input(f"Domain [{domain}]: ").strip()
            domain = domain_input or domain
    else:
        # Non-interactive: use defaults
        if not name:
            name = cwd.name.lower().replace(" ", "-")
        if port is None:
            port = 0

    # Create config
    config = {
        "name": name,
        "port": port if port else None,  # None means auto
        "domain": domain,
        "auto_register": True,
        "auto_caddy": True,
    }

    # Remove None values for cleaner YAML
    config = {k: v for k, v in config.items() if v is not None}

    try:
        import yaml

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        msg_success(f"Created {config_file}")
        print()
        print("Next steps:")
        print("  1. Add to your app: from devhost_cli.runner import run")
        print("  2. Replace app.run() with: run(app)")
        print(f"  3. Access at: http://{name}.{domain}")
        print()
        return True
    except Exception as e:
        msg_error(f"Failed to create config: {e}")
        return False


def ensure_admin_if_needed(command: str, args: list[str], domain: str) -> None:
    """Relaunch with admin privileges if needed"""
    if not IS_WINDOWS or is_admin():
        return
    if "--elevated" in sys.argv:
        msg_info("Administrator privileges are required for this operation.")
        return
    if command == "domain" and args:
        domain = args[0]
    if domain == "localhost":
        return
    if command in {"add", "remove", "hosts", "domain"}:
        msg_warning("⚠️  Administrator privileges required to update Windows hosts file.")
        msg_info("Re-launching as Administrator...")
        relaunch_as_admin([command] + args)
        sys.exit(0)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Devhost - Lightweight local development domain router",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--version", action="version", version=f"devhost {__version__}")
    parser.add_argument("--elevated", action="store_true", help=argparse.SUPPRESS)

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # add command
    add_parser = subparsers.add_parser("add", help="Add a new mapping")
    add_parser.add_argument("name", help="Service name (e.g., myapp)")
    add_parser.add_argument("target", help="Port or host:port or URL")
    add_parser.add_argument("--http", action="store_const", const="http", dest="scheme", help="Force HTTP")
    add_parser.add_argument("--https", action="store_const", const="https", dest="scheme", help="Force HTTPS")

    # remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a mapping")
    remove_parser.add_argument("name", help="Service name to remove")

    # list command
    list_parser = subparsers.add_parser("list", help="List all mappings")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # url command
    url_parser = subparsers.add_parser("url", help="Get URL for a mapping")
    url_parser.add_argument("name", nargs="?", help="Service name (uses first if omitted)")

    # open command
    open_parser = subparsers.add_parser("open", help="Open mapping in browser")
    open_parser.add_argument("name", nargs="?", help="Service name (uses first if omitted)")

    # validate command
    subparsers.add_parser("validate", help="Validate configuration and services")

    # export command
    export_parser = subparsers.add_parser("export", help="Print generated Caddyfile")
    export_parser.add_argument("what", nargs="?", default="")

    # edit command
    subparsers.add_parser("edit", help="Open devhost.json in editor")

    # resolve command
    resolve_parser = subparsers.add_parser("resolve", help="Show resolution details")
    resolve_parser.add_argument("name", help="Service name")

    # doctor command
    doctor_parser = subparsers.add_parser("doctor", help="Run comprehensive diagnostics")
    doctor_parser.add_argument("--windows", action="store_true")
    doctor_parser.add_argument("--fix", action="store_true")

    # fix-http command
    subparsers.add_parser("fix-http", help="Convert https mappings to http")

    # info command
    subparsers.add_parser("info", help="Show help")

    # hosts command (Windows)
    hosts_parser = subparsers.add_parser("hosts", help="Manage Windows hosts entries")
    hosts_parser.add_argument("action", choices=["sync", "clear"])

    # caddy command (Windows)
    caddy_parser = subparsers.add_parser("caddy", help="Manage Caddy (Windows)")
    caddy_parser.add_argument("action", choices=["start", "stop", "restart", "status"])

    # domain command
    domain_parser = subparsers.add_parser("domain", help="Get or set base domain")
    domain_parser.add_argument("name", nargs="?", help="Domain name to set")

    # init command
    init_parser = subparsers.add_parser("init", help="Create devhost.yml project config")
    init_parser.add_argument("--name", "-n", help="App name (default: directory name)")
    init_parser.add_argument("--port", "-p", type=int, help="Port number (default: auto)")
    init_parser.add_argument("--domain", "-d", default="localhost", help="Base domain (default: localhost)")
    init_parser.add_argument("--yes", "-y", action="store_true", help="Accept defaults without prompting")

    # start command
    subparsers.add_parser("start", help="Start router process (and Caddy on Windows)")

    # stop command
    subparsers.add_parser("stop", help="Stop router process")

    # status command
    status_parser = subparsers.add_parser("status", help="Show current mode and health summary")
    status_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # integrity command
    integrity_parser = subparsers.add_parser("integrity", help="Check file integrity")
    integrity_parser.add_argument("action", nargs="?", default="check", choices=["check"], help="Integrity action")

    # qr command
    qr_parser = subparsers.add_parser("qr", help="Show QR code for mobile access")
    qr_parser.add_argument("name", nargs="?", help="Service name (uses first if omitted)")

    # oauth command
    oauth_parser = subparsers.add_parser("oauth", help="Show OAuth redirect URIs")
    oauth_parser.add_argument("name", nargs="?", help="Service name (uses first if omitted)")

    # env command
    env_parser = subparsers.add_parser("env", help="Environment file management")
    env_parser.add_argument("action", choices=["sync"], help="Action: sync")
    env_parser.add_argument("--name", "-n", help="Service name (uses first if omitted)")
    env_parser.add_argument("--file", "-f", default=".env", help="Env file path (default: .env)")
    env_parser.add_argument("--dry-run", action="store_true", help="Show what would change")

    # install command
    install_parser = subparsers.add_parser("install", help="Run installer")
    install_parser.add_argument("--windows", action="store_true")
    install_parser.add_argument("--macos", action="store_true")
    install_parser.add_argument("--linux", action="store_true")
    install_parser.add_argument("--caddy", action="store_true")
    install_parser.add_argument("--yes", "-y", action="store_true")
    install_parser.add_argument("--dry-run", action="store_true")
    install_parser.add_argument("--start-dns", action="store_true")
    install_parser.add_argument("--install-completions", action="store_true")
    install_parser.add_argument("--domain")
    install_parser.add_argument("--uvicorn")
    install_parser.add_argument("--user")
    install_parser.add_argument("--clean", action="store_true")
    install_parser.add_argument("rest", nargs=argparse.REMAINDER)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    if args.command in {"add", "remove", "hosts", "domain"}:
        ensure_admin_if_needed(
            args.command,
            [a for a in sys.argv[2:] if a != "--elevated"],
            Config().get_domain(),
        )

    cli = DevhostCLI()

    try:
        if args.command == "add":
            success = cli.add(args.name, args.target, args.scheme)
        elif args.command == "remove":
            success = cli.remove(args.name)
        elif args.command == "list":
            success = cli.list_mappings(args.json)
        elif args.command == "url":
            success = cli.url(args.name)
        elif args.command == "open":
            success = cli.open_browser(args.name)
        elif args.command == "validate":
            success = cli.validate()
        elif args.command == "resolve":
            success = cli.resolve(args.name)
        elif args.command == "doctor":
            if args.windows or IS_WINDOWS:
                doctor_windows(fix=args.fix)
                success = True
            else:
                success = cli.doctor()
        elif args.command == "fix-http":
            success = cli.fix_http()
        elif args.command == "info":
            parser.print_help()
            success = True
        elif args.command == "export":
            if args.what == "caddy":
                success = cli.export_caddy()
            else:
                msg_error("Usage: devhost export caddy")
                success = False
        elif args.command == "edit":
            success = cli.edit()
        elif args.command == "hosts":
            if not IS_WINDOWS:
                msg_error("Hosts management is supported on Windows only.")
                success = False
            elif not is_admin():
                msg_error("⚠️  Administrator privileges required for hosts file management.")
                msg_info("Please run this command from an elevated PowerShell.")
                success = False
            else:
                if args.action == "sync":
                    hosts_sync()
                else:
                    hosts_clear()
                success = True
        elif args.command == "caddy":
            if not IS_WINDOWS:
                msg_error("Caddy management is supported on Windows only.")
                success = False
            else:
                if args.action == "start":
                    caddy_start()
                elif args.action == "stop":
                    caddy_stop()
                elif args.action == "restart":
                    caddy_restart()
                else:
                    caddy_status()
                success = True
        elif args.command == "domain":
            if args.name:
                success = cli.config.set_domain(args.name)
            else:
                print(cli.config.get_domain())
                success = True
        elif args.command == "init":
            success = handle_init(args)
        elif args.command == "start":
            success = cli.router.start()
        elif args.command == "stop":
            success = cli.router.stop()
        elif args.command == "status":
            if args.json:
                success = cli.router.status(args.json)
            else:
                success = cli.status()
        elif args.command == "integrity":
            success = cli.integrity_check()
        elif args.command == "qr":
            from .features import show_qr_for_route

            success = show_qr_for_route(args.name)
        elif args.command == "oauth":
            from .features import show_oauth_for_route

            success = show_oauth_for_route(args.name)
        elif args.command == "env":
            from .features import sync_env_file

            if args.action == "sync":
                success = sync_env_file(args.name, args.file, args.dry_run)
            else:
                msg_error(f"Unknown env action: {args.action}")
                success = False
        elif args.command == "install":
            script_dir = Path(__file__).parent.parent.resolve()
            install_script = script_dir / "install.py"
            if not install_script.exists():
                msg_error("install.py not found.")
                success = False
            else:
                cmd = [sys.executable, str(install_script)] + sys.argv[2:]
                result = subprocess.run(cmd, check=False)
                success = result.returncode == 0
        else:
            parser.print_help()
            return 1

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130
    except Exception as e:
        msg_error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
