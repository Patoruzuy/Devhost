"""CLI command implementations"""

import json
import platform
import socket
import sys
import webbrowser
from pathlib import Path

from .caddy import edit_config, generate_caddyfile, print_caddyfile
from .config import Config
from .platform import IS_WINDOWS, is_admin
from .router import Router
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

    def add(self, name: str, target: str, scheme: str | None = None):
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
        msg_info(f"Access your app at: {target_scheme}://{name}.{domain}")
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

        if IS_WINDOWS:
            domain = self.config.get_domain()
            if domain != "localhost" and is_admin():
                hosts_remove(f"{name}.{domain}")

        domain = self.config.get_domain()
        msg_success(f"Removed mapping: {name}.{domain}")
        return True

    def list_mappings(self, json_output: bool = False):
        """List all mappings"""
        routes = self.config.load()
        domain = self.config.get_domain()

        if json_output:
            print(json.dumps(routes, indent=2))
            return True

        if not routes:
            msg_info("No mappings yet")
            msg_info("Add one with: devhost add <name> <port>")
            return True

        print(f"\n{Colors.BLUE}Configured Routes:{Colors.RESET}\n")

        for name, target in sorted(routes.items()):
            parsed = parse_target(str(target))
            if parsed:
                scheme, host, port = parsed
                url = f"{scheme}://{name}.{domain}"
                target_str = f"{scheme}://{host}:{port}"

                # Check if service is running
                status = ""
                if check_port_open(host, port, timeout=0.5):
                    status = f"{Colors.GREEN}+{Colors.RESET}"
                else:
                    status = f"{Colors.RED}-{Colors.RESET}"

                print(f"  {status} {Colors.BLUE}{url:30}{Colors.RESET} -> {target_str}")
            else:
                print(f"  ? {name}.{domain:30} -> {target} (invalid)")

        print()
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
        scheme = get_dev_scheme(target)
        url = f"{scheme}://{name}.{domain}"
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
        url = f"{scheme}://{name}.{domain}"

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
        config_file = Path(__file__).parent.parent.resolve() / "devhost.json"
        if config_file.exists():
            try:
                self.config.load()
                msg_success(f"Config file: {config_file}")
            except Exception as e:
                msg_error(f"Config file invalid: {e}")
        else:
            msg_warning("Config file not found (will be created)")

        # Check router
        if self.router._check_health():
            msg_success("Router: responding on :5555")
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

    def doctor(self):
        """Run comprehensive diagnostics"""
        print(f"\n{Colors.BLUE}Devhost Doctor{Colors.RESET}\n")

        # Platform info
        print(f"Platform: {platform.system()} {platform.release()}")
        print(f"Python: {sys.version.split()[0]}")
        print()

        # Run validation
        self.validate()

        # Router details
        running, pid = self.router.is_running()
        if running:
            msg_success(f"Router process: running{f' (pid {pid})' if pid else ''}")
            msg_info(f"Logs: {self.router.log_file}")
        else:
            msg_error("Router process: not running")

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

    def edit(self):
        """Open config in editor"""
        edit_config()
        return True
