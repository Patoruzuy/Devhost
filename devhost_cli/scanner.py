"""
Devhost TUI - Port Scanner

Ghost port detection using psutil to find listening processes.
"""

from dataclasses import dataclass


@dataclass
class ListeningPort:
    """Information about a listening port."""

    port: int
    pid: int
    name: str
    status: str = "LISTEN"


def scan_listening_ports(exclude_system: bool = True) -> list[ListeningPort]:
    """
    Scan for listening TCP ports on the system.

    Returns a list of ListeningPort objects.

    Args:
        exclude_system: If True, exclude system ports (<1024) and common system processes
    """
    try:
        import psutil
    except ImportError:
        # psutil not installed, return empty list
        return []

    ports = []
    seen_ports = set()

    # Common system processes to exclude
    system_processes = {
        "System",
        "svchost",
        "services",
        "lsass",
        "wininit",
        "csrss",
        "smss",
        "spoolsv",
        "SearchIndexer",
        "MsMpEng",
    }

    try:
        for conn in psutil.net_connections(kind="tcp"):
            # Only interested in listening connections
            if conn.status != "LISTEN":
                continue

            # Get local address
            if not conn.laddr:
                continue

            port = conn.laddr.port
            pid = conn.pid

            # Skip if we've already seen this port
            if port in seen_ports:
                continue
            seen_ports.add(port)

            # Skip system ports if requested
            if exclude_system and port < 1024:
                continue

            # Get process name
            name = "unknown"
            if pid:
                try:
                    proc = psutil.Process(pid)
                    name = proc.name()

                    # Skip system processes if requested
                    if exclude_system and name in system_processes:
                        continue
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            ports.append(
                ListeningPort(
                    port=port,
                    pid=pid or 0,
                    name=name,
                    status="LISTEN",
                )
            )

    except (psutil.AccessDenied, PermissionError):
        # May need admin privileges on some systems
        pass

    # Sort by port number
    ports.sort(key=lambda p: p.port)
    return ports


def get_common_dev_ports() -> dict[int, str]:
    """Get mapping of common development ports to descriptions."""
    return {
        3000: "React/Node.js dev server",
        3001: "React/Node.js dev server (alternate)",
        4000: "Phoenix/Gatsby dev server",
        4200: "Angular dev server",
        5000: "Flask/ASP.NET dev server",
        5173: "Vite dev server",
        5174: "Vite dev server (alternate)",
        5432: "PostgreSQL",
        5500: "Live Server",
        6379: "Redis",
        7777: "Devhost Gateway",
        8000: "Django/uvicorn/Python HTTP",
        8080: "General HTTP/Proxy",
        8081: "General HTTP (alternate)",
        8443: "HTTPS dev",
        8888: "Jupyter Notebook",
        9000: "PHP-FPM/SonarQube",
        9090: "Prometheus",
        27017: "MongoDB",
    }


def detect_framework(name: str, port: int) -> str | None:
    """
    Try to detect the framework based on process name and port.

    Returns framework name or None.
    """
    name_lower = name.lower()

    # Python frameworks
    if "python" in name_lower or "uvicorn" in name_lower:
        if port == 8000:
            return "Django/FastAPI"
        if port == 5000:
            return "Flask"
        return "Python"

    # Node.js frameworks
    if "node" in name_lower:
        if port == 3000:
            return "React/Express"
        if port == 4200:
            return "Angular"
        if port in (5173, 5174):
            return "Vite"
        return "Node.js"

    # Ruby
    if "ruby" in name_lower:
        if port == 3000:
            return "Rails"
        return "Ruby"

    # PHP
    if "php" in name_lower:
        return "PHP"

    # Go
    if "go" in name_lower:
        return "Go"

    # Java
    if "java" in name_lower:
        return "Java/Spring"

    # Databases
    if "postgres" in name_lower or port == 5432:
        return "PostgreSQL"
    if "mysql" in name_lower or "mariadb" in name_lower:
        return "MySQL/MariaDB"
    if "mongod" in name_lower or port == 27017:
        return "MongoDB"
    if "redis" in name_lower or port == 6379:
        return "Redis"

    return None


def format_port_list(ports: list[ListeningPort]) -> str:
    """Format a list of ports for display."""
    if not ports:
        return "No listening ports found"

    common_ports = get_common_dev_ports()
    lines = []

    for p in ports:
        framework = detect_framework(p.name, p.port)
        desc = common_ports.get(p.port, "")

        if framework:
            lines.append(f"  {p.port:5d}  {p.name:20s}  [{framework}]")
        elif desc:
            lines.append(f"  {p.port:5d}  {p.name:20s}  ({desc})")
        else:
            lines.append(f"  {p.port:5d}  {p.name:20s}")

    return "\n".join(lines)
