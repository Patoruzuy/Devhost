"""
Rich-powered console output for Devhost v3.0

Provides styled tables, status panels, and consistent formatting.
"""

import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Global console instance with force_terminal=False to respect TTY detection
# and legacy_windows=True for better Windows compatibility
console = Console(force_terminal=None, legacy_windows=True)

# Check if we should use ASCII-safe characters (non-TTY or Windows legacy console)
_USE_ASCII = not sys.stdout.isatty()

# Mode badges and colors - with ASCII fallbacks
MODE_STYLES = {
    "off": ("O" if _USE_ASCII else "⭘", "dim"),
    "gateway": ("G" if _USE_ASCII else "🌐", "cyan"),
    "system": ("S" if _USE_ASCII else "🔧", "green"),
    "external": ("E" if _USE_ASCII else "🔗", "yellow"),
}

STATUS_STYLES = {
    "ok": ("+" if _USE_ASCII else "✓", "green"),
    "error": ("x" if _USE_ASCII else "✗", "red"),
    "warning": ("!" if _USE_ASCII else "!", "yellow"),
    "info": ("i" if _USE_ASCII else "ℹ", "blue"),
    "running": ("+" if _USE_ASCII else "●", "green"),
    "stopped": ("-" if _USE_ASCII else "○", "dim"),
}


def print_success(message: str):
    """Print a success message"""
    icon = "+" if _USE_ASCII else "✓"
    console.print(f"[green]{icon}[/green] {message}")


def print_error(message: str):
    """Print an error message"""
    icon = "x" if _USE_ASCII else "✗"
    console.print(f"[red]{icon}[/red] {message}", style="red")


def print_warning(message: str):
    """Print a warning message"""
    console.print(f"[yellow]![/yellow] {message}")


def print_info(message: str):
    """Print an info message"""
    icon = "i" if _USE_ASCII else "ℹ"
    console.print(f"[blue]{icon}[/blue] {message}")


def print_step(current: int, total: int, message: str):
    """Print a step in a process"""
    console.print(f"[dim][{current}/{total}][/dim] {message}")


def mode_badge(mode: str) -> Text:
    """Create a styled mode badge"""
    icon, style = MODE_STYLES.get(mode, ("?", "dim"))
    text = Text()
    text.append(f"{icon} ", style=style)
    text.append(mode, style=f"bold {style}")
    return text


def status_icon(status: str) -> Text:
    """Create a styled status icon"""
    icon, style = STATUS_STYLES.get(status, ("?", "dim"))
    return Text(icon, style=style)


def routes_table(routes: dict, domain: str = "localhost", mode: str = "gateway", port: int = 7777) -> Table:
    """
    Create a Rich table showing all routes.

    Args:
        routes: Dict of route_name -> route_config
        domain: Base domain
        mode: Current proxy mode
        port: Gateway port (for mode 1)
    """
    table = Table(title="Routes", show_header=True, header_style="bold cyan")

    table.add_column("Name", style="bold")
    table.add_column("URL", style="cyan")
    table.add_column("Upstream", style="dim")
    table.add_column("Status", justify="center")

    if not routes:
        return table

    for name, config in routes.items():
        # Determine URL based on mode
        route_domain = config.get("domain", domain)
        if mode == "gateway":
            url = f"http://{name}.{route_domain}:{port}"
        elif mode == "system":
            url = f"http://{name}.{route_domain}"
        elif mode == "external":
            url = f"http://{name}.{route_domain}"
        else:
            url = "[dim](mode off)[/dim]"

        # Get upstream
        upstream = config.get("upstream", "?")
        if isinstance(upstream, int):
            upstream = f"127.0.0.1:{upstream}"

        # Status
        enabled = config.get("enabled", True)
        status = status_icon("running" if enabled else "stopped")

        table.add_row(name, url, upstream, status)

    return table


def status_panel(mode: str, route_count: int, gateway_port: int = 7777, health_info: dict | None = None) -> Panel:
    """
    Create a status panel showing current mode and health.

    Args:
        mode: Current proxy mode
        route_count: Number of registered routes
        gateway_port: Gateway listen port
        health_info: Optional dict with health details
    """
    lines = []

    # Mode line
    badge = mode_badge(mode)
    lines.append(Text.assemble("Mode: ", badge))

    # Route count
    lines.append(Text(f"Routes: {route_count}"))

    # Mode-specific info
    if mode == "gateway":
        lines.append(Text(f"Gateway: 127.0.0.1:{gateway_port}"))
    elif mode == "system":
        lines.append(Text("System Proxy: localhost:80"))
    elif mode == "external":
        lines.append(Text("External Proxy: attached"))

    # Health info
    if health_info:
        if health_info.get("proxy_running"):
            lines.append(Text.assemble(status_icon("running"), " Proxy running"))
        else:
            lines.append(Text.assemble(status_icon("stopped"), " Proxy stopped"))

        if health_info.get("integrity_issues"):
            count = health_info["integrity_issues"]
            lines.append(Text.assemble(status_icon("warning"), f" {count} integrity issue(s)"))

    content = Text("\n").join(lines)
    return Panel(content, title="Devhost Status", border_style="cyan")


def integrity_table(results: dict[str, tuple[bool, str]]) -> Table:
    """
    Create a table showing integrity check results.

    Args:
        results: Dict of filepath -> (ok, status)
    """
    table = Table(title="Integrity Check", show_header=True, header_style="bold")

    table.add_column("File", style="dim")
    table.add_column("Status", justify="center")

    for filepath, (_ok, status) in results.items():
        # Shorten path for display
        from pathlib import Path

        path = Path(filepath)
        display_path = f"~/{path.relative_to(Path.home())}" if str(path).startswith(str(Path.home())) else str(path)

        if status == "ok":
            status_text = Text("✓ OK", style="green")
        elif status == "modified":
            status_text = Text("! Modified", style="yellow")
        elif status == "missing":
            status_text = Text("✗ Missing", style="red")
        else:
            status_text = Text("- Untracked", style="dim")

        table.add_row(display_path, status_text)

    return table


def doctor_panel(checks: list[tuple[str, bool, str]]) -> Panel:
    """
    Create a diagnostic panel for devhost doctor.

    Args:
        checks: List of (check_name, passed, message)
    """
    lines = []

    for check_name, passed, message in checks:
        if passed:
            icon = status_icon("ok")
        else:
            icon = status_icon("error")

        lines.append(Text.assemble(icon, f" {check_name}: ", Text(message, style="dim" if passed else "yellow")))

    content = Text("\n").join(lines)
    return Panel(content, title="System Check", border_style="cyan")


def print_routes(routes: dict, domain: str = "localhost", mode: str = "gateway", port: int = 7777):
    """Print the routes table"""
    table = routes_table(routes, domain, mode, port)
    console.print(table)


def print_status(mode: str, route_count: int, gateway_port: int = 7777, health_info: dict | None = None):
    """Print the status panel"""
    panel = status_panel(mode, route_count, gateway_port, health_info)
    console.print(panel)


def print_integrity(results: dict[str, tuple[bool, str]]):
    """Print integrity check results"""
    table = integrity_table(results)
    console.print(table)


def print_doctor(checks: list[tuple[str, bool, str]]):
    """Print doctor diagnostics"""
    panel = doctor_panel(checks)
    console.print(panel)
