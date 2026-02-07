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
from .windows import caddy_restart, caddy_start, caddy_status, caddy_stop, doctor_windows, hosts_clear, hosts_restore, hosts_sync


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
    add_parser.add_argument(
        "--upstream",
        action="append",
        dest="extra_upstreams",
        help="Additional upstreams (tcp:host:port, lan:host:port, docker:host:port, unix:/path)",
    )

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

    # diagnostics command
    diagnostics_parser = subparsers.add_parser("diagnostics", help="Export diagnostic bundle")
    diagnostics_subparsers = diagnostics_parser.add_subparsers(dest="diagnostics_action", help="Diagnostics action")
    diagnostics_preview = diagnostics_subparsers.add_parser("preview", help="Preview diagnostic bundle contents")
    diagnostics_preview.add_argument("--no-state", action="store_true", help="Exclude state.yml")
    diagnostics_preview.add_argument("--no-config", action="store_true", help="Exclude devhost.json and domain")
    diagnostics_preview.add_argument("--no-proxy", action="store_true", help="Exclude proxy snippets")
    diagnostics_preview.add_argument("--no-logs", action="store_true", help="Exclude logs")
    diagnostics_preview.add_argument("--top", type=int, default=30, help="Show top N largest files (default: 30)")
    diagnostics_preview.add_argument(
        "--max-size",
        help="Maximum bundle size (e.g. 50MB). Use 0 or --no-size-limit to disable.",
    )
    diagnostics_preview.add_argument("--no-size-limit", action="store_true", help="Disable size limit enforcement")
    diagnostics_preview.add_argument("--redaction-file", help="Path to redaction config file")
    preview_redact = diagnostics_preview.add_mutually_exclusive_group()
    preview_redact.add_argument("--redact", action="store_true", help="Redact secrets in preview (default)")
    preview_redact.add_argument("--no-redact", action="store_true", help="Disable redaction")

    diagnostics_upload = diagnostics_subparsers.add_parser("upload", help="Prepare bundle and show upload steps")
    diagnostics_upload.add_argument(
        "--max-size",
        help="Maximum bundle size (e.g. 50MB). Use 0 or --no-size-limit to disable.",
    )
    diagnostics_upload.add_argument("--no-size-limit", action="store_true", help="Disable size limit enforcement")
    diagnostics_upload.add_argument("--redaction-file", help="Path to redaction config file")
    upload_redact = diagnostics_upload.add_mutually_exclusive_group()
    upload_redact.add_argument("--redact", action="store_true", help="Redact secrets in bundle (default)")
    upload_redact.add_argument("--no-redact", action="store_true", help="Disable redaction")

    diagnostics_export = diagnostics_subparsers.add_parser("export", help="Export diagnostic bundle")
    diagnostics_export.add_argument("--output", "-o", help="Output path for bundle (.zip)")
    diagnostics_export.add_argument("--no-state", action="store_true", help="Exclude state.yml")
    diagnostics_export.add_argument("--no-config", action="store_true", help="Exclude devhost.json and domain")
    diagnostics_export.add_argument("--no-proxy", action="store_true", help="Exclude proxy snippets")
    diagnostics_export.add_argument("--no-logs", action="store_true", help="Exclude logs")
    diagnostics_export.add_argument(
        "--max-size",
        help="Maximum bundle size (e.g. 50MB). Use 0 or --no-size-limit to disable.",
    )
    diagnostics_export.add_argument("--no-size-limit", action="store_true", help="Disable size limit enforcement")
    diagnostics_export.add_argument("--redaction-file", help="Path to redaction config file")
    redact_group = diagnostics_export.add_mutually_exclusive_group()
    redact_group.add_argument("--redact", action="store_true", help="Redact secrets in bundle (default)")
    redact_group.add_argument("--no-redact", action="store_true", help="Disable redaction")

    # fix-http command
    subparsers.add_parser("fix-http", help="Convert https mappings to http")

    # scan command
    scan_parser = subparsers.add_parser("scan", help="Scan for listening ports (ghost port detection)")
    scan_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # info command
    subparsers.add_parser("info", help="Show help")

    # hosts command (Windows)
    hosts_parser = subparsers.add_parser("hosts", help="Manage Windows hosts entries")
    hosts_parser.add_argument("action", choices=["sync", "clear", "restore"])

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

    # proxy command (external proxy integration)
    proxy_parser = subparsers.add_parser("proxy", help="Proxy management (Mode 2/3)")
    proxy_subparsers = proxy_parser.add_subparsers(dest="proxy_action", help="Proxy action")

    # proxy start
    proxy_subparsers.add_parser("start", help="Start proxy (Mode 2: system)")

    # proxy stop
    proxy_stop_parser = proxy_subparsers.add_parser("stop", help="Stop proxy (Mode 2: system)")
    proxy_stop_parser.add_argument("--force", "-f", action="store_true", help="Force stop even with active routes")

    # proxy status
    proxy_subparsers.add_parser("status", help="Show proxy status")

    # proxy reload
    proxy_subparsers.add_parser("reload", help="Reload proxy config (Mode 2: system)")

    # proxy upgrade
    proxy_upgrade_parser = proxy_subparsers.add_parser("upgrade", help="Upgrade proxy mode")
    proxy_upgrade_parser.add_argument(
        "--to", dest="to_mode", choices=["gateway", "system"], required=True, help="Target mode"
    )

    # proxy expose
    proxy_expose_parser = proxy_subparsers.add_parser("expose", help="Bind proxy to LAN or localhost")
    expose_group = proxy_expose_parser.add_mutually_exclusive_group(required=True)
    expose_group.add_argument("--lan", action="store_true", help="Bind to 0.0.0.0 (LAN access)")
    expose_group.add_argument("--local", action="store_true", help="Bind to 127.0.0.1 (localhost only)")
    expose_group.add_argument("--iface", help="Bind to a specific interface IP (e.g. 192.168.1.10)")
    proxy_expose_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    # proxy export
    proxy_export_parser = proxy_subparsers.add_parser("export", help="Export proxy config snippets")
    proxy_export_parser.add_argument(
        "--driver", "-d", choices=["caddy", "nginx", "traefik"], help="Specific driver (default: all)"
    )
    proxy_export_parser.add_argument("--show", "-s", action="store_true", help="Print snippet without saving")
    proxy_export_parser.add_argument("--use-lock", action="store_true", help="Generate from lockfile")
    proxy_export_parser.add_argument("--lock-path", help="Path to lockfile (default: ~/.devhost/devhost.lock.json)")

    # proxy discover
    proxy_subparsers.add_parser("discover", help="Discover proxy config files")

    # proxy attach
    proxy_attach_parser = proxy_subparsers.add_parser("attach", help="Attach devhost to proxy config")
    proxy_attach_parser.add_argument("driver", choices=["caddy", "nginx", "traefik"], help="Proxy driver")
    proxy_attach_parser.add_argument("--config-path", "-c", help="Path to proxy config file")
    proxy_attach_parser.add_argument("--no-validate", action="store_true", help="Skip proxy config validation")
    proxy_attach_parser.add_argument("--use-lock", action="store_true", help="Use lockfile for snippet generation")
    proxy_attach_parser.add_argument("--lock-path", help="Path to lockfile (default: ~/.devhost/devhost.lock.json)")

    # proxy detach
    proxy_detach_parser = proxy_subparsers.add_parser("detach", help="Detach devhost from proxy config")
    proxy_detach_parser.add_argument("--config-path", "-c", help="Path to proxy config file")
    proxy_detach_parser.add_argument("--force", action="store_true", help="Detach even if marker block drifted")

    # proxy drift
    proxy_drift_parser = proxy_subparsers.add_parser("drift", help="Check external proxy drift")
    proxy_drift_parser.add_argument("--driver", "-d", choices=["caddy", "nginx", "traefik"], help="Proxy driver")
    proxy_drift_parser.add_argument("--config-path", "-c", help="Path to proxy config file")
    proxy_drift_parser.add_argument("--validate", action="store_true", help="Run proxy validator")
    proxy_drift_parser.add_argument("--accept", action="store_true", help="Accept current files as baseline")

    # proxy validate
    proxy_validate_parser = proxy_subparsers.add_parser("validate", help="Validate external proxy config")
    proxy_validate_parser.add_argument("--driver", "-d", choices=["caddy", "nginx", "traefik"], help="Proxy driver")
    proxy_validate_parser.add_argument("--config-path", "-c", help="Path to proxy config file")

    # proxy lock
    proxy_lock_parser = proxy_subparsers.add_parser("lock", help="Manage proxy lockfile")
    lock_subparsers = proxy_lock_parser.add_subparsers(dest="lock_action", help="Lockfile action")
    lock_write = lock_subparsers.add_parser("write", help="Write lockfile from current routes")
    lock_write.add_argument("--path", "-p", help="Path to lockfile (default: ~/.devhost/devhost.lock.json)")
    lock_apply = lock_subparsers.add_parser("apply", help="Apply lockfile to state")
    lock_apply.add_argument("--path", "-p", help="Path to lockfile (default: ~/.devhost/devhost.lock.json)")
    lock_apply.add_argument("--no-config", action="store_true", help="Do not update devhost.json")
    lock_show = lock_subparsers.add_parser("show", help="Show lockfile contents")
    lock_show.add_argument("--path", "-p", help="Path to lockfile (default: ~/.devhost/devhost.lock.json)")

    # proxy sync
    proxy_sync_parser = proxy_subparsers.add_parser("sync", help="Sync proxy snippets")
    proxy_sync_parser.add_argument("--driver", "-d", choices=["caddy", "nginx", "traefik"], help="Proxy driver")
    proxy_sync_parser.add_argument("--watch", "-w", action="store_true", help="Watch for changes")
    proxy_sync_parser.add_argument("--interval", type=float, default=2.0, help="Polling interval (seconds)")
    proxy_sync_parser.add_argument("--use-lock", action="store_true", help="Sync from lockfile")
    proxy_sync_parser.add_argument("--lock-path", help="Path to lockfile (default: ~/.devhost/devhost.lock.json)")

    # proxy cleanup
    proxy_cleanup_parser = proxy_subparsers.add_parser("cleanup", help="Remove Devhost-managed proxy files")
    proxy_cleanup_parser.add_argument("--system", action="store_true", help="Remove system-mode Caddyfile")
    proxy_cleanup_parser.add_argument("--external", action="store_true", help="Remove external snippets/manifests")
    proxy_cleanup_parser.add_argument("--lock", action="store_true", help="Remove proxy lockfile")
    proxy_cleanup_parser.add_argument("--all", action="store_true", help="Remove all Devhost-managed proxy files")
    proxy_cleanup_parser.add_argument("--dry-run", action="store_true", help="Show what would be removed")
    proxy_cleanup_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    # proxy transfer
    proxy_transfer_parser = proxy_subparsers.add_parser("transfer", help="Transfer to external proxy mode")
    proxy_transfer_parser.add_argument("driver", choices=["caddy", "nginx", "traefik"], help="Proxy driver")
    proxy_transfer_parser.add_argument("--config-path", "-c", help="Path to proxy config file")
    proxy_transfer_parser.add_argument("--no-attach", action="store_true", help="Skip attaching to config")
    proxy_transfer_parser.add_argument("--no-verify", action="store_true", help="Skip route verification")
    proxy_transfer_parser.add_argument("--port", "-p", type=int, default=80, help="Proxy port (default: 80)")

    # tunnel command (Phase 6: expose local services to internet)
    tunnel_parser = subparsers.add_parser("tunnel", help="Tunnel management (expose to internet)")
    tunnel_subparsers = tunnel_parser.add_subparsers(dest="tunnel_action", help="Tunnel action")

    # tunnel start
    tunnel_start_parser = tunnel_subparsers.add_parser("start", help="Start tunnel for a route")
    tunnel_start_parser.add_argument("name", nargs="?", help="Route name (uses first if omitted)")
    tunnel_start_parser.add_argument(
        "--provider", "-p", choices=["cloudflared", "ngrok", "localtunnel"], help="Tunnel provider"
    )

    # tunnel stop
    tunnel_stop_parser = tunnel_subparsers.add_parser("stop", help="Stop tunnel")
    tunnel_stop_parser.add_argument("name", nargs="?", help="Route name (stops all if omitted)")

    # tunnel status
    tunnel_subparsers.add_parser("status", help="Show active tunnels")

    # dashboard command (TUI)
    subparsers.add_parser("dashboard", help="Open interactive TUI dashboard")

    # logs command
    logs_parser = subparsers.add_parser("logs", help="Tail router logs")
    logs_parser.add_argument("-f", "--follow", action="store_true", help="Follow log output (like tail -f)")
    logs_parser.add_argument("-n", "--lines", type=int, default=50, help="Number of lines to show (default: 50)")
    logs_parser.add_argument("--clear", action="store_true", help="Clear log file")

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
            success = cli.add(args.name, args.target, args.scheme, args.extra_upstreams)
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
        elif args.command == "diagnostics":
            if args.diagnostics_action == "preview":
                redact = True
                if getattr(args, "no_redact", False):
                    redact = False
                success = cli.diagnostics_preview(
                    include_state=not args.no_state,
                    include_config=not args.no_config,
                    include_proxy=not args.no_proxy,
                    include_logs=not args.no_logs,
                    redact=redact,
                    top=args.top,
                    redaction_file=Path(args.redaction_file) if args.redaction_file else None,
                    size_limit=args.max_size,
                    no_size_limit=args.no_size_limit,
                )
            elif args.diagnostics_action == "upload":
                redact = True
                if getattr(args, "no_redact", False):
                    redact = False
                success = cli.diagnostics_upload(
                    redact=redact,
                    redaction_file=Path(args.redaction_file) if args.redaction_file else None,
                    size_limit=args.max_size,
                    no_size_limit=args.no_size_limit,
                )
            elif args.diagnostics_action == "export":
                redact = True
                if getattr(args, "no_redact", False):
                    redact = False
                success = cli.diagnostics_export(
                    output_path=args.output,
                    include_state=not args.no_state,
                    include_config=not args.no_config,
                    include_proxy=not args.no_proxy,
                    include_logs=not args.no_logs,
                    redact=redact,
                    redaction_file=Path(args.redaction_file) if args.redaction_file else None,
                    size_limit=args.max_size,
                    no_size_limit=args.no_size_limit,
                )
            else:
                msg_info(
                    "Usage: devhost diagnostics preview|export|upload [--output PATH] "
                    "[--no-state|--no-config|--no-proxy|--no-logs] "
                    "[--max-size SIZE|--no-size-limit] [--no-redact]"
                )
                success = True
        elif args.command == "fix-http":
            success = cli.fix_http()
        elif args.command == "scan":
            success = cli.scan(json_output=args.json)
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
                elif args.action == "clear":
                    hosts_clear()
                else:
                    hosts_restore()
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
        elif args.command == "proxy":
            from .caddy_lifecycle import (
                cmd_proxy_reload,
                cmd_proxy_start,
                cmd_proxy_status,
                cmd_proxy_stop,
                cmd_proxy_upgrade,
                cmd_proxy_expose,
            )
            from .proxy import (
                cmd_proxy_attach,
                cmd_proxy_cleanup,
                cmd_proxy_detach,
                cmd_proxy_discover,
                cmd_proxy_drift,
                cmd_proxy_export,
                cmd_proxy_lock,
                cmd_proxy_sync,
                cmd_proxy_transfer,
                cmd_proxy_validate,
            )

            if args.proxy_action == "start":
                success = cmd_proxy_start()
            elif args.proxy_action == "stop":
                success = cmd_proxy_stop(args.force)
            elif args.proxy_action == "status":
                success = cmd_proxy_status()
            elif args.proxy_action == "reload":
                success = cmd_proxy_reload()
            elif args.proxy_action == "upgrade":
                success = cmd_proxy_upgrade(args.to_mode)
            elif args.proxy_action == "expose":
                mode = "lan" if args.lan else "local"
                success = cmd_proxy_expose(mode, args.iface, args.yes)
            elif args.proxy_action == "export":
                cmd_proxy_export(
                    args.driver,
                    args.show,
                    use_lock=args.use_lock,
                    lock_path=Path(args.lock_path) if args.lock_path else None,
                )
                success = True
            elif args.proxy_action == "discover":
                cmd_proxy_discover()
                success = True
            elif args.proxy_action == "attach":
                cmd_proxy_attach(
                    args.driver,
                    args.config_path,
                    no_validate=args.no_validate,
                    use_lock=args.use_lock,
                    lock_path=Path(args.lock_path) if args.lock_path else None,
                )
                success = True
            elif args.proxy_action == "detach":
                cmd_proxy_detach(args.config_path, force=args.force)
                success = True
            elif args.proxy_action == "drift":
                cmd_proxy_drift(
                    driver=args.driver,
                    config_path=args.config_path,
                    validate=args.validate,
                    accept=args.accept,
                )
                success = True
            elif args.proxy_action == "validate":
                cmd_proxy_validate(driver=args.driver, config_path=args.config_path)
                success = True
            elif args.proxy_action == "lock":
                cmd_proxy_lock(args.lock_action, path=args.path, no_config=getattr(args, "no_config", False))
                success = True
            elif args.proxy_action == "sync":
                cmd_proxy_sync(
                    driver=args.driver,
                    watch=args.watch,
                    interval=args.interval,
                    use_lock=args.use_lock,
                    lock_path=Path(args.lock_path) if args.lock_path else None,
                )
                success = True
            elif args.proxy_action == "cleanup":
                cmd_proxy_cleanup(
                    include_system=args.system,
                    include_external=args.external,
                    include_lock=args.lock,
                    include_all=args.all,
                    dry_run=args.dry_run,
                    assume_yes=args.yes,
                )
                success = True
            elif args.proxy_action == "transfer":
                cmd_proxy_transfer(
                    args.driver,
                    args.config_path,
                    args.no_attach,
                    args.no_verify,
                    args.port,
                )
                success = True
            else:
                msg_info(
                    "Usage: devhost proxy {start|stop|status|reload|upgrade|expose|export|discover|attach|detach|drift|validate|lock|sync|cleanup|transfer}"
                )
                success = True
        elif args.command == "tunnel":
            from .tunnel import cmd_tunnel_start, cmd_tunnel_status, cmd_tunnel_stop

            if args.tunnel_action == "start":
                success = cmd_tunnel_start(args.name, args.provider)
            elif args.tunnel_action == "stop":
                success = cmd_tunnel_stop(args.name)
            elif args.tunnel_action == "status":
                success = cmd_tunnel_status()
            else:
                msg_info("Usage: devhost tunnel {start|stop|status}")
                success = True
        elif args.command == "dashboard":
            try:
                from devhost_tui.app import DevhostDashboard
            except ImportError:
                msg_error("TUI dependencies not installed. Install with: pip install devhost[tui]")
                success = False
            else:
                app = DevhostDashboard()
                app.run()
                success = True
        elif args.command == "logs":
            from .logs import cmd_logs

            success = cmd_logs(follow=args.follow, lines=args.lines, clear=args.clear)
        elif args.command == "install":
            from .installer import main as installer_main

            success = installer_main(sys.argv[2:]) == 0
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
