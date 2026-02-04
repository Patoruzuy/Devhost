"""
Developer features for Devhost v3.0

Provides OAuth helper, QR code generation, and env sync.
"""

import socket
import sys
from pathlib import Path

from .config import Config
from .output import console, print_error, print_info, print_success, print_warning
from .state import StateConfig

# Common OAuth callback paths
OAUTH_CALLBACK_PATHS = [
    "/callback",
    "/oauth/callback",
    "/auth/callback",
    "/api/auth/callback",
    "/auth/google/callback",
    "/auth/github/callback",
    "/auth/facebook/callback",
    "/login/callback",
    "/oauth2/callback",
]

# OAuth library patterns to detect
OAUTH_LIBRARIES = {
    "flask": ["flask-dance", "authlib", "flask-oauthlib", "flask-login"],
    "django": ["social-auth-app-django", "django-allauth", "django-oauth-toolkit"],
    "fastapi": ["authlib", "fastapi-users", "python-jose"],
}


def get_lan_ip() -> str | None:
    """Get the LAN IP address of this machine."""
    try:
        # Create a socket and connect to an external address
        # This doesn't actually send data, just determines the route
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # Fallback: try to get from hostname
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if ip.startswith("127."):
                return None
            return ip
        except Exception:
            return None


def detect_oauth_libraries() -> list[str]:
    """Detect installed OAuth libraries by checking imports."""
    detected = []

    # Check for common OAuth packages
    packages_to_check = [
        "flask_dance",
        "authlib",
        "flask_oauthlib",
        "social_django",
        "allauth",
        "oauth_toolkit",
        "fastapi_users",
        "jose",
    ]

    for pkg in packages_to_check:
        try:
            __import__(pkg)
            detected.append(pkg)
        except ImportError:
            pass

    return detected


def get_oauth_uris(name: str, domain: str = "localhost", port: int | None = None) -> list[str]:
    """
    Generate OAuth redirect URIs for a given app.

    Args:
        name: App name (subdomain)
        domain: Base domain
        port: Optional port (for gateway mode)

    Returns:
        List of OAuth redirect URIs
    """
    if port:
        base_url = f"http://{name}.{domain}:{port}"
    else:
        base_url = f"http://{name}.{domain}"

    return [f"{base_url}{path}" for path in OAUTH_CALLBACK_PATHS]


def print_oauth_uris(name: str, domain: str = "localhost", port: int | None = None, framework: str | None = None):
    """Print OAuth redirect URIs with Rich formatting."""
    uris = get_oauth_uris(name, domain, port)
    detected_libs = detect_oauth_libraries()

    console.print()
    if framework:
        console.print(f"[bold cyan]Framework:[/bold cyan] {framework}")

    if port:
        console.print(f"[bold cyan]Access URL:[/bold cyan] http://{name}.{domain}:{port}")
    else:
        console.print(f"[bold cyan]Access URL:[/bold cyan] http://{name}.{domain}")

    console.print()
    console.print("[bold yellow]OAuth Redirect URIs:[/bold yellow]")
    for uri in uris[:5]:  # Show top 5 most common
        console.print(f"   {uri}")

    console.print()
    console.print("[dim]Add these to your OAuth provider's allowed redirect URIs.[/dim]")

    if detected_libs:
        console.print()
        console.print(f"[dim]Detected OAuth libraries: {', '.join(detected_libs)}[/dim]")


def generate_qr_code(url: str, quiet: bool = False) -> str | None:
    """
    Generate a QR code for terminal display.

    Args:
        url: URL to encode
        quiet: If True, return the QR string without printing

    Returns:
        QR code as string if quiet=True, else None
    """
    try:
        import segno
    except ImportError:
        print_error("segno not installed. Run: pip install devhost[qr]")
        return None

    qr = segno.make(url)

    # Generate terminal-friendly output
    # Use ASCII mode for better compatibility
    if sys.stdout.isatty():
        # Full Unicode blocks for TTY
        qr_str = qr.terminal(compact=True)
    else:
        # ASCII fallback for non-TTY
        import io

        buffer = io.StringIO()
        qr.terminal(out=buffer, compact=True)
        qr_str = buffer.getvalue()

    if quiet:
        return qr_str

    return qr_str


def show_qr_for_route(name: str | None = None):
    """
    Show QR code for accessing a route from mobile/LAN.

    Args:
        name: Route name (uses first route if None)
    """
    config = Config()
    routes = config.load()

    if not routes:
        print_error("No routes configured")
        print_info("Add one with: devhost add <name> <port>")
        return False

    # Use first route if no name specified
    if not name:
        name = sorted(routes.keys())[0]

    if name not in routes:
        print_error(f"No route found for '{name}'")
        return False

    # Get route details
    target = routes[name]

    # Parse port from target
    port = None
    if isinstance(target, int):
        port = target
    elif isinstance(target, str):
        if target.isdigit():
            port = int(target)
        elif ":" in target:
            try:
                port = int(target.split(":")[-1].split("/")[0])
            except ValueError:
                pass

    if not port:
        print_error(f"Could not determine port for '{name}'")
        return False

    # Get LAN IP
    lan_ip = get_lan_ip()
    if not lan_ip:
        print_warning("Could not determine LAN IP address")
        lan_ip = "localhost"

    # Generate URL for mobile access (direct to port, not through proxy)
    mobile_url = f"http://{lan_ip}:{port}"

    console.print()
    console.print(f"[bold cyan]QR Code for:[/bold cyan] {name}")
    console.print()

    # Generate and print QR code
    qr_str = generate_qr_code(mobile_url)
    if qr_str:
        console.print(qr_str)

    console.print()
    console.print(f"[bold green]Scan to access:[/bold green] {mobile_url}")
    console.print("[dim](Make sure your phone is on the same network)[/dim]")
    console.print()

    return True


def sync_env_file(name: str | None = None, env_file: str = ".env", dry_run: bool = False) -> bool:
    """
    Sync .env file with current devhost URL.

    Updates or adds:
    - APP_URL
    - ALLOWED_HOSTS
    - BASE_URL (if exists)

    Args:
        name: Route name (uses first route if None)
        env_file: Path to .env file
        dry_run: If True, print what would change without modifying

    Returns:
        True if successful
    """
    config = Config()
    state = StateConfig()
    routes = config.load()

    if not routes:
        print_error("No routes configured")
        return False

    # Use first route if no name specified
    if not name:
        name = sorted(routes.keys())[0]

    if name not in routes:
        print_error(f"No route found for '{name}'")
        return False

    # Determine URL based on mode
    domain = config.get_domain()
    mode = state.proxy_mode
    port = state.gateway_port

    if mode == "gateway":
        url = f"http://{name}.{domain}:{port}"
    else:
        url = f"http://{name}.{domain}"

    # Variables to sync
    updates = {
        "APP_URL": url,
        "ALLOWED_HOSTS": f"{name}.{domain}",
        "BASE_URL": url,
    }

    env_path = Path(env_file)

    # Read existing .env
    existing_vars = {}
    if env_path.exists():
        try:
            content = env_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    existing_vars[key.strip()] = value.strip()
        except OSError as e:
            print_error(f"Failed to read {env_file}: {e}")
            return False

    # Determine what to update
    changes = {}
    for key, value in updates.items():
        # Only update APP_URL and ALLOWED_HOSTS by default
        # Only update BASE_URL if it already exists
        if key == "BASE_URL" and key not in existing_vars:
            continue

        if existing_vars.get(key) != value:
            changes[key] = value

    if not changes:
        print_info("No changes needed - .env is already in sync")
        return True

    if dry_run:
        console.print()
        console.print("[bold yellow]Would update .env:[/bold yellow]")
        for key, value in changes.items():
            old = existing_vars.get(key, "(not set)")
            console.print(f"   {key}: {old} -> {value}")
        return True

    # Apply changes
    existing_vars.update(changes)

    # Write back
    try:
        lines = []
        for key, value in existing_vars.items():
            # Quote value if it contains spaces
            if " " in value and not (value.startswith('"') or value.startswith("'")):
                value = f'"{value}"'
            lines.append(f"{key}={value}")

        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        print_success(f"Updated {env_file}:")
        for key, value in changes.items():
            console.print(f"   {key}={value}")

        return True

    except OSError as e:
        print_error(f"Failed to write {env_file}: {e}")
        return False


def show_oauth_for_route(name: str | None = None):
    """
    Show OAuth redirect URIs for a route.

    Args:
        name: Route name (uses first route if None)
    """
    config = Config()
    state = StateConfig()
    routes = config.load()

    if not routes:
        print_error("No routes configured")
        print_info("Add one with: devhost add <name> <port>")
        return False

    # Use first route if no name specified
    if not name:
        name = sorted(routes.keys())[0]

    if name not in routes:
        print_error(f"No route found for '{name}'")
        return False

    domain = config.get_domain()
    mode = state.proxy_mode

    if mode == "gateway":
        port = state.gateway_port
        print_oauth_uris(name, domain, port)
    else:
        print_oauth_uris(name, domain)

    return True
