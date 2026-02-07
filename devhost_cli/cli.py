"""CLI command implementations"""

import json
import platform
import socket
import sys
import webbrowser
from pathlib import Path

from .caddy import edit_config, generate_caddyfile, print_caddyfile
from .config import Config
from .output import console, print_info, print_routes, print_success, print_warning
from .platform import IS_WINDOWS, is_admin
from .proxy import parse_upstream_entry
from .router_manager import Router
from .state import StateConfig
from .utils import Colors, msg_error, msg_info, msg_step, msg_success, msg_warning
from .validation import get_dev_scheme, parse_target, validate_name
from .windows import hosts_add, hosts_remove


def check_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except OSError:
        return False


def read_single_key() -> str | None:
    """Read a single keypress (non-blocking)"""
    if not sys.stdin.isatty():
        return None
    if IS_WINDOWS:
        try:
            import msvcrt

            ch = msvcrt.getch()
            try:
                return ch.decode("utf-8")
            except Exception:
                return None
        except Exception:
            return None
    else:
        try:
            import termios
            import tty

            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                return sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            return None


class DevhostCLI:
    """Main CLI interface"""

    def __init__(self):
        self.config = Config()
        self.router = Router()

    def _access_url(self, name: str, domain: str, target: object | None = None) -> str:
        """Build the user-facing access URL based on current proxy mode."""
        try:
            state = StateConfig()
            mode = state.proxy_mode
            gateway_port = state.gateway_port
        except Exception:
            mode = "gateway"
            gateway_port = 7777

        if mode == "gateway":
            return f"http://{name}.{domain}:{gateway_port}"
        if mode in ("system", "external"):
            scheme = get_dev_scheme(target)
            return f"{scheme}://{name}.{domain}"
        if target is not None:
            parsed = parse_target(str(target))
            if parsed:
                upstream_scheme, host, port = parsed
                return f"{upstream_scheme}://{host}:{port}"
        return f"http://{name}.{domain}:{gateway_port}"

    def add(self, name: str, target: str, scheme: str | None = None, extra_upstreams: list[str] | None = None):
        """Add a new mapping"""
        msg_step(1, 4, "Validating inputs...")

        if not validate_name(name):
            return False
        if not target:
            msg_error("Usage: devhost add <name> <port|host:port>")
            return False

        if scheme and (target.startswith("http://") or target.startswith("https://")):
            msg_error("Target already includes a scheme; do not combine with --http/--https")
            return False

        raw_target = target
        if scheme:
            if raw_target.isdigit():
                raw_target = f"127.0.0.1:{raw_target}"
            raw_target = f"{scheme}://{raw_target}"

        parsed = parse_target(raw_target)
        if not parsed:
            return False

        target_scheme, host, port = parsed

        msg_step(2, 4, "Adding mapping to configuration...")

        routes = self.config.load()

        # Store as port number if simple localhost mapping, else keep raw target
        if (not scheme) and raw_target.isdigit():
            routes[name] = port
        else:
            routes[name] = raw_target

        self.config.save(routes)
        generate_caddyfile(routes)

        if IS_WINDOWS:
            domain = self.config.get_domain()
            if domain != "localhost":
                if is_admin():
                    hosts_add(f"{name}.{domain}")
                else:
                    msg_warning("Hosts update skipped (not running as Administrator).")

        domain = self.config.get_domain()
        msg_success(f"Added mapping: {name}.{domain} -> {target_scheme}://{host}:{port}")
        if extra_upstreams:
            msg_info("Additional upstreams saved for external proxy exports.")

        # Keep v3 state routes in sync (Mode 2/3 tooling relies on this)
        try:
            state = StateConfig()
            upstream = f"{host}:{port}"
            if target_scheme == "https":
                upstream = f"https://{upstream}"
            upstream_specs: list[dict] = []
            primary_spec = parse_upstream_entry(raw_target)
            if primary_spec:
                upstream_specs.append(primary_spec)

            if extra_upstreams:
                for raw in extra_upstreams:
                    spec = parse_upstream_entry(raw)
                    if not spec:
                        msg_warning(f"Skipping invalid upstream: {raw}")
                        continue
                    upstream_specs.append(spec)

            state.set_route(
                name,
                upstream=upstream,
                domain=domain,
                enabled=True,
                upstreams=upstream_specs or None,
            )
        except Exception:
            pass

        msg_step(3, 4, "Checking if service is reachable...")
        if check_port_open(host, port):
            msg_success(f"Service is running on {host}:{port}")
        else:
            msg_warning(f"Service not responding on {host}:{port}")
            msg_info("Make sure your application is running on this port")

        msg_step(4, 4, "Checking router status...")
        if not self.router.is_running()[0]:
            msg_warning("Router is not running")
            msg_info("Start it with: devhost start")
        else:
            msg_success("Router is running")

        print()
        msg_info(f"Access your app at: {self._access_url(name, domain, routes.get(name))}")
        return True

    def remove(self, name: str):
        """Remove a mapping"""
        routes = self.config.load()

        if name not in routes:
            domain = self.config.get_domain()
            msg_error(f"No mapping found for {name}.{domain}")
            return False

        del routes[name]
        self.config.save(routes)
        generate_caddyfile(routes)

        try:
            StateConfig().remove_route(name)
        except Exception:
            pass

        if IS_WINDOWS:
            domain = self.config.get_domain()
            if domain != "localhost" and is_admin():
                hosts_remove(f"{name}.{domain}")

        domain = self.config.get_domain()
        msg_success(f"Removed mapping: {name}.{domain}")
        return True

    def list_mappings(self, json_output: bool = False):
        """List all mappings with Rich table output"""
        routes = self.config.load()
        domain = self.config.get_domain()

        if json_output:
            print(json.dumps(routes, indent=2))
            return True

        if not routes:
            print_info("No mappings yet")
            print_info("Add one with: devhost add <name> <port>")
            return True

        # Convert legacy format to Rich-compatible format
        rich_routes = {}
        for name, target in routes.items():
            parsed = parse_target(str(target))
            if parsed:
                upstream_scheme, host, port = parsed
                # Check if service is running
                is_running = check_port_open(host, port, timeout=0.5)
                upstream = f"{host}:{port}"
                if upstream_scheme == "https":
                    upstream = f"https://{upstream}"
                rich_routes[name] = {
                    "upstream": upstream,
                    "domain": domain,
                    "scheme": "http",
                    "enabled": is_running,
                }
            else:
                rich_routes[name] = {
                    "upstream": str(target),
                    "domain": domain,
                    "scheme": "http",
                    "enabled": False,
                }

        # Get state for mode info
        try:
            state = StateConfig()
            mode = state.proxy_mode
            port = state.gateway_port
        except Exception:
            mode = "gateway"
            port = 7777

        print_routes(rich_routes, domain, mode, port)
        return True

    def url(self, name: str | None = None):
        """Get URL for a mapping"""
        routes = self.config.load()
        domain = self.config.get_domain()

        if not routes:
            msg_error("No mappings configured")
            return False

        # Use first mapping if no name specified
        if not name:
            name = sorted(routes.keys())[0]

        if name not in routes:
            msg_error(f"No mapping found for {name}")
            return False

        target = routes[name]
        url = self._access_url(name, domain, target)
        print(url)
        if sys.stdin.isatty():
            print("Press Ctrl+O to open in browser, any other key to skip...", end=" ", flush=True)
            key = read_single_key()
            print()
            if key == "\x0f":
                webbrowser.open(url)
        return True

    def open_browser(self, name: str | None = None):
        """Open mapping in browser"""
        routes = self.config.load()
        domain = self.config.get_domain()

        if not routes:
            msg_error("No mappings configured")
            return False

        # Use first mapping if no name specified
        if not name:
            name = sorted(routes.keys())[0]

        if name not in routes:
            msg_error(f"No mapping found for {name}")
            return False

        target = routes[name]
        parsed = parse_target(str(target))
        if not parsed:
            msg_error(f"Invalid target for {name}")
            return False

        scheme, host, port = parsed
        url = self._access_url(name, domain, target)

        msg_info(f"Opening {url}...")
        if webbrowser.open(url):
            return True
        msg_error("Failed to open browser.")
        msg_info(f"Manually open: {url}")
        return False

    def validate(self):
        """Quick validation of configuration and services"""
        print(f"\n{Colors.BLUE}Devhost Validation{Colors.RESET}\n")

        # Check config file
        config_file = self.config.config_file
        if config_file.exists():
            try:
                self.config.load()
                msg_success(f"Config file: {config_file}")
            except Exception as e:
                msg_error(f"Config file invalid: {e}")
        else:
            msg_warning("Config file not found (will be created)")

        # Check router
        gateway_port = 7777
        try:
            gateway_port = StateConfig().gateway_port
        except Exception:
            pass

        if self.router._check_health():
            msg_success(f"Router: responding on :{gateway_port}")
        else:
            msg_error("Router: not responding")
            msg_info("Start with: devhost start")

        # Check first mapping's DNS
        routes = self.config.load()
        if routes:
            name = sorted(routes.keys())[0]
            domain = self.config.get_domain()
            fqdn = f"{name}.{domain}"

            # Try to resolve
            try:
                socket.gethostbyname(fqdn)
                msg_success(f"DNS: {fqdn} resolves")
            except socket.gaierror:
                msg_error(f"DNS: {fqdn} does not resolve")
                msg_info("DNS setup may be needed for wildcard domains")

        print()
        return True

    def resolve(self, name: str):
        """Show resolution details for a mapping"""
        routes = self.config.load()
        domain = self.config.get_domain()

        if name not in routes:
            msg_error(f"No mapping found for {name}")
            return False

        target = routes[name]
        parsed = parse_target(str(target))
        if not parsed:
            msg_error(f"Invalid target for {name}")
            return False

        scheme, host, port = parsed
        fqdn = f"{name}.{domain}"

        print(f"\n{Colors.BLUE}Resolution for {name}:{Colors.RESET}\n")
        print(f"  Domain: {fqdn}")
        print(f"  Target: {scheme}://{host}:{port}")

        # DNS resolution
        try:
            ip = socket.gethostbyname(fqdn)
            msg_success(f"DNS: {fqdn} -> {ip}")
        except socket.gaierror:
            msg_error(f"DNS: {fqdn} does not resolve")

        # Port check
        if check_port_open(host, port):
            msg_success(f"Port: {host}:{port} is open")
        else:
            msg_error(f"Port: {host}:{port} is not reachable")

        print()
        return True

    def status(self):
        """Show current mode and health summary with Rich styling"""
        from .output import print_integrity, print_status

        try:
            state = StateConfig()
            mode = state.proxy_mode
            route_count = len(self.config.load())
            gateway_port = state.gateway_port

            # Check proxy health
            running, pid = self.router.is_running()
            proxy_health = self.router._check_health() if running else None

            # Check integrity
            integrity_results = state.check_all_integrity()
            integrity_issues = sum(1 for ok, _ in integrity_results.values() if not ok)

            health_info = {
                "proxy_running": running,
                "proxy_pid": pid,
                "proxy_health": proxy_health,
                "integrity_issues": integrity_issues,
            }

            print_status(mode, route_count, gateway_port, health_info)

            # Show integrity issues if any
            if integrity_issues > 0:
                print()
                print_integrity(integrity_results)

        except Exception as e:
            msg_error(f"Failed to get status: {e}")
            return False

        return True

    def integrity_check(self):
        """Check integrity of all tracked files"""
        from .output import print_integrity

        try:
            state = StateConfig()
            results = state.check_all_integrity()

            if not results:
                print_info("No files are being tracked for integrity")
                return True

            print_integrity(results)

            issues = sum(1 for ok, _ in results.values() if not ok)
            if issues > 0:
                print_warning(f"{issues} file(s) have changed since last recorded")
            else:
                print_success("All tracked files are intact")

        except Exception as e:
            msg_error(f"Failed to check integrity: {e}")
            return False

        return True

    def doctor(self):
        """Run comprehensive diagnostics with Rich output"""
        from .output import print_doctor

        checks = []

        # Platform info
        console.print(f"[bold]Platform:[/bold] {platform.system()} {platform.release()}")
        console.print(f"[bold]Python:[/bold] {sys.version.split()[0]}")
        console.print()

        # Config file check
        config_file = self.config.config_file
        if config_file.exists():
            try:
                self.config.load()
                checks.append(("Config file", True, str(config_file)))
            except Exception as e:
                checks.append(("Config file", False, f"Invalid: {e}"))
        else:
            checks.append(("Config file", True, "Will be created on first use"))

        # Router check
        running, pid = self.router.is_running()
        if running:
            checks.append(("Router", True, f"Running (pid {pid})" if pid else "Running"))
        else:
            checks.append(("Router", False, "Not running - start with: devhost start"))

        # State file check
        try:
            state = StateConfig()
            checks.append(("State file", True, str(state.state_file)))
            checks.append(("Proxy mode", True, state.proxy_mode))
        except Exception as e:
            checks.append(("State file", False, str(e)))

        # DNS check for first mapping
        routes = self.config.load()
        if routes:
            name = sorted(routes.keys())[0]
            domain = self.config.get_domain()
            fqdn = f"{name}.{domain}"
            try:
                socket.gethostbyname(fqdn)
                checks.append(("DNS resolution", True, f"{fqdn} resolves"))
            except socket.gaierror:
                checks.append(("DNS resolution", False, f"{fqdn} does not resolve"))
        else:
            checks.append(("DNS resolution", True, "No routes to check"))

        # Integrity check
        try:
            state = StateConfig()
            integrity_results = state.check_all_integrity()
            issues = sum(1 for ok, _ in integrity_results.values() if not ok)
            if issues > 0:
                checks.append(("Integrity", False, f"{issues} file(s) modified"))
            elif integrity_results:
                checks.append(("Integrity", True, f"{len(integrity_results)} file(s) tracked"))
            else:
                checks.append(("Integrity", True, "No files tracked"))
        except Exception:
            checks.append(("Integrity", True, "Not configured"))

        print_doctor(checks)
        print()
        return True

    def fix_http(self):
        """Convert https mappings to http"""
        routes = self.config.load()
        if not routes:
            msg_info("No mappings configured")
            return True

        changed = {}
        for name, value in routes.items():
            if isinstance(value, str) and value.startswith("https://"):
                routes[name] = "http://" + value[len("https://") :]
                changed[name] = routes[name]

        if not changed:
            msg_info("No https mappings found")
            return True

        self.config.save(routes)
        generate_caddyfile(routes)
        msg_success(f"Updated {len(changed)} mapping(s) to http")
        for name, target in sorted(changed.items()):
            msg_info(f"{name} -> {target}")
        return True

    def export_caddy(self):
        """Print generated Caddyfile"""
        print_caddyfile(self.config.load())
        return True

    def diagnostics_export(
        self,
        output_path: str | None = None,
        include_state: bool = True,
        include_config: bool = True,
        include_proxy: bool = True,
        include_logs: bool = True,
        redact: bool = True,
        redaction_file: Path | None = None,
        size_limit: str | int | None = None,
        no_size_limit: bool = False,
    ) -> bool:
        """Export a diagnostic bundle for support."""
        from .diagnostics import _format_bytes, export_diagnostic_bundle, parse_size_limit

        try:
            if not redact:
                msg_warning("Redaction disabled. Bundle may contain secrets.")
            size_limit_bytes: int | None = None
            if no_size_limit:
                size_limit_bytes = 0
            elif size_limit is not None:
                size_limit_bytes = parse_size_limit(size_limit)
            state = StateConfig()
            success, bundle_path, manifest = export_diagnostic_bundle(
                state,
                output_path=Path(output_path) if output_path else None,
                include_state=include_state,
                include_config=include_config,
                include_proxy=include_proxy,
                include_logs=include_logs,
                redact=redact,
                redaction_file=redaction_file,
                size_limit_bytes=size_limit_bytes,
            )
            if success and bundle_path:
                count = len(manifest.get("included", []))
                msg_success(f"Diagnostic bundle saved: {bundle_path} ({count} files)")
                missing = manifest.get("missing", [])
                if missing:
                    msg_warning(f"Missing files: {len(missing)} (not found)")
                errors = manifest.get("redaction_config", {}).get("errors", [])
                if errors:
                    msg_warning(f"Redaction config errors: {len(errors)}")
                size_limit_val = manifest.get("options", {}).get("size_limit_bytes")
                if size_limit_val:
                    msg_info(f"Bundle size limit: {_format_bytes(size_limit_val)}")
            else:
                msg_error(f"Failed to export diagnostics: {manifest.get('error', 'unknown error')}")
            return success
        except ValueError as exc:
            msg_error(str(exc))
            return False
        except Exception as exc:
            msg_error(f"Failed to export diagnostics: {exc}")
            return False

    def diagnostics_preview(
        self,
        include_state: bool = True,
        include_config: bool = True,
        include_proxy: bool = True,
        include_logs: bool = True,
        redact: bool = True,
        top: int = 30,
        redaction_file: Path | None = None,
        size_limit: str | int | None = None,
        no_size_limit: bool = False,
    ) -> bool:
        """Preview diagnostic bundle contents without writing a zip."""
        from .diagnostics import _format_bytes, parse_size_limit, preview_diagnostic_bundle

        try:
            if not redact:
                msg_warning("Redaction disabled. Preview may include sensitive filenames.")
            size_limit_bytes: int | None = None
            if no_size_limit:
                size_limit_bytes = 0
            elif size_limit is not None:
                size_limit_bytes = parse_size_limit(size_limit)
            state = StateConfig()
            preview = preview_diagnostic_bundle(
                state,
                include_state=include_state,
                include_config=include_config,
                include_proxy=include_proxy,
                include_logs=include_logs,
                redact=redact,
                redaction_file=redaction_file,
                size_limit_bytes=size_limit_bytes,
            )
            included = preview.get("included_sorted") or preview["included"]
            missing = preview["missing"]
            total = preview["total_size"]
            redacted_count = preview["redacted_count"]
            msg_info(f"Preview: {len(included)} files, {_format_bytes(total)} total")
            if preview.get("size_limit_human"):
                msg_info(f"Size limit: {preview['size_limit_human']}")
            if preview.get("over_limit"):
                msg_warning("Bundle exceeds size limit.")
            if redacted_count:
                msg_info(f"Redaction will apply to {redacted_count} file(s)")
            errors = preview.get("redaction_config", {}).get("errors", [])
            if errors:
                msg_warning(f"Redaction config errors: {len(errors)}")
            if missing:
                msg_warning(f"Missing files: {len(missing)}")
            for item in included[:top]:
                suffix = " [redacted]" if item["redact"] else ""
                msg_info(f"  {item['path']} ({_format_bytes(item['size'])}){suffix}")
            if len(included) > top:
                msg_info(f"  …and {len(included) - top} more")
            return True
        except ValueError as exc:
            msg_error(str(exc))
            return False
        except Exception as exc:
            msg_error(f"Failed to preview diagnostics: {exc}")
            return False

    def diagnostics_upload(
        self,
        redact: bool = True,
        redaction_file: Path | None = None,
        size_limit: str | int | None = None,
        no_size_limit: bool = False,
    ) -> bool:
        """Prepare a diagnostic bundle in a temp path with upload instructions."""
        import tempfile

        from .diagnostics import _format_bytes, export_diagnostic_bundle, parse_size_limit

        try:
            if not redact:
                msg_warning("Redaction disabled. Bundle may contain secrets.")
            size_limit_bytes: int | None = None
            if no_size_limit:
                size_limit_bytes = 0
            elif size_limit is not None:
                size_limit_bytes = parse_size_limit(size_limit)
            state = StateConfig()
            temp_dir = Path(tempfile.gettempdir()) / "devhost-diagnostics"
            success, bundle_path, manifest = export_diagnostic_bundle(
                state,
                output_path=temp_dir,
                redact=redact,
                redaction_file=redaction_file,
                size_limit_bytes=size_limit_bytes,
            )
            if success and bundle_path:
                msg_success(f"Diagnostic bundle prepared: {bundle_path}")
                msg_info("Next steps:")
                msg_info("  1. Review the bundle contents")
                msg_info("  2. Upload it to your support channel (do not post publicly)")
                msg_info("  3. Delete it after sharing if no longer needed")
                missing = manifest.get("missing", [])
                if missing:
                    msg_warning(f"Missing files: {len(missing)}")
                size_limit_val = manifest.get("options", {}).get("size_limit_bytes")
                if size_limit_val:
                    msg_info(f"Bundle size limit: {_format_bytes(size_limit_val)}")
                return True
            msg_error(f"Failed to prepare diagnostics: {manifest.get('error', 'unknown error')}")
            return False
        except ValueError as exc:
            msg_error(str(exc))
            return False
        except Exception as exc:
            msg_error(f"Failed to prepare diagnostics: {exc}")
            return False

    def edit(self):
        """Open config in editor"""
        edit_config()
        return True

    def scan(self, json_output: bool = False):
        """Scan for listening ports on the system (ghost port detection)."""
        from devhost_cli.scanner import detect_framework, format_port_list, get_common_dev_ports, scan_listening_ports

        msg_info("Scanning for listening ports...")
        ports = scan_listening_ports(exclude_system=True)

        if not ports:
            msg_warning("No listening ports found.")
            msg_info("Tip: Start your application and run 'devhost scan' again.")
            msg_info("Note: Port scanning requires psutil. Install with: pip install psutil")
            return True

        if json_output:
            import json as json_lib

            output = [
                {
                    "port": p.port,
                    "pid": p.pid,
                    "process": p.name,
                    "framework": detect_framework(p.name, p.port),
                    "description": get_common_dev_ports().get(p.port),
                }
                for p in ports
            ]
            console.print(json_lib.dumps(output, indent=2))
            return True

        # Pretty output
        msg_success(f"Found {len(ports)} listening port(s):")
        console.print()

        common_ports = get_common_dev_ports()
        for p in ports:
            framework = detect_framework(p.name, p.port)
            desc = common_ports.get(p.port)

            # Emoji based on detection
            emoji = "🐍" if "python" in p.name.lower() else "🟢"
            if framework:
                emoji = {"Python": "🐍", "Node.js": "🟢", "PostgreSQL": "🐘", "Redis": "🔴", "MongoDB": "🍃"}.get(
                    framework.split("/")[0], "🟢"
                )

            line = f"{emoji} Port [cyan]{p.port:5d}[/cyan]  {p.name:20s}"
            if framework:
                line += f"  [yellow][{framework}][/yellow]"
            elif desc:
                line += f"  [dim]({desc})[/dim]"
            line += f"  [dim](PID {p.pid})[/dim]"

            console.print(line)

        console.print()
        msg_info("To add a route quickly: devhost add <name> <port>")
        msg_info("For guided setup: devhost dashboard (then press A or type /add)")
        return True
