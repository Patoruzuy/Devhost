"""
External proxy integration for Devhost v3.0

Provides snippet generation, attach/detach, discovery, and transfer for:
- Caddy
- Nginx
- Traefik
"""

import hashlib
import json
import re
import shutil
import subprocess
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx

from devhost_cli import __version__
from devhost_cli.config import Config

from .output import console, print_error, print_info, print_success, print_warning
from .state import StateConfig
from .validation import parse_target

ProxyDriver = Literal["caddy", "nginx", "traefik"]

# Marker comments for attach/detach
MARKER_BEGIN = "# devhost: begin"
MARKER_END = "# devhost: end"

LOCKFILE_NAME = "devhost.lock.json"


@dataclass(frozen=True)
class UpstreamSpec:
    type: str
    target: str


@dataclass(frozen=True)
class RouteSpec:
    name: str
    domain: str
    enabled: bool
    upstreams: tuple[UpstreamSpec, ...]


def _normalize_tcp_target(raw: str | int) -> str | None:
    if isinstance(raw, int):
        parsed = parse_target(str(raw))
    else:
        parsed = parse_target(str(raw))
    if not parsed:
        return None
    scheme, host, port = parsed
    return f"{scheme}://{host}:{port}"


def _normalize_upstream(entry) -> UpstreamSpec | None:
    if entry is None:
        return None
    if isinstance(entry, dict):
        upstream_type = str(entry.get("type", "tcp")).lower()
        target = entry.get("target")
        if upstream_type == "unix":
            if not target:
                return None
            return UpstreamSpec(type="unix", target=str(target))
        if upstream_type in {"tcp", "lan", "docker"}:
            normalized = _normalize_tcp_target(target)
            if not normalized:
                return None
            return UpstreamSpec(type=upstream_type, target=normalized)
        # Unknown types are ignored for safety
        return None

    # simple scalar target (port, host:port, URL)
    normalized = _normalize_tcp_target(entry)
    if not normalized:
        return None
    return UpstreamSpec(type="tcp", target=normalized)


def _normalize_upstreams(value) -> tuple[UpstreamSpec, ...]:
    items: list[UpstreamSpec] = []
    if isinstance(value, list):
        for entry in value:
            spec = _normalize_upstream(entry)
            if spec:
                items.append(spec)
    else:
        spec = _normalize_upstream(value)
        if spec:
            items.append(spec)

    # Stable ordering
    items.sort(key=lambda spec: (spec.type, spec.target))
    return tuple(items)


def parse_upstream_entry(value: str) -> dict[str, str] | None:
    """
    Parse a user-provided upstream string into a normalized dict.

    Accepts:
    - tcp:host:port / lan:host:port / docker:host:port
    - unix:/path or unix:///path
    - raw targets (port, host:port, http(s)://host:port)
    """
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None

    upstream_type = None
    target = raw

    if raw.startswith("unix://"):
        upstream_type = "unix"
        target = raw[len("unix://") :]
    elif raw.startswith("unix:"):
        upstream_type = "unix"
        target = raw[len("unix:") :]
    elif ":" in raw:
        prefix, rest = raw.split(":", 1)
        if prefix in {"tcp", "lan", "docker", "unix"}:
            upstream_type = prefix
            target = rest
            if upstream_type == "unix" and target.startswith("//"):
                target = target[2:]

    entry = {"type": upstream_type, "target": target} if upstream_type else raw
    spec = _normalize_upstream(entry)
    if not spec:
        return None
    return {"type": spec.type, "target": spec.target}


def _route_sort_key(route: RouteSpec) -> tuple:
    upstream_key = tuple((u.type, u.target) for u in route.upstreams)
    return (route.domain, route.name, upstream_key)


def _routes_payload(routes: Iterable[RouteSpec]) -> list[dict]:
    payload = []
    for route in sorted(routes, key=_route_sort_key):
        payload.append(
            {
                "name": route.name,
                "domain": route.domain,
                "enabled": bool(route.enabled),
                "upstreams": [{"type": u.type, "target": u.target} for u in route.upstreams],
            }
        )
    return payload


def _routes_hash(routes: Iterable[RouteSpec]) -> str:
    payload = _routes_payload(routes)
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _snippet_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _split_tcp_target(target: str) -> tuple[str, str, int] | None:
    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.hostname or not parsed.port:
        return None
    return parsed.scheme, parsed.hostname, parsed.port


def _lockfile_path(config: Config | None = None) -> Path:
    cfg = config or Config()
    return cfg.script_dir / LOCKFILE_NAME


def _load_lockfile(path: Path | None = None) -> dict | None:
    lock_path = path or _lockfile_path()
    if not lock_path.exists():
        return None
    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _route_specs_from_lock(lock: dict) -> list[RouteSpec]:
    routes_in = lock.get("routes", [])
    routes: list[RouteSpec] = []
    for item in routes_in:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        domain = str(item.get("domain", "")).strip() or lock.get("domain", "localhost")
        enabled = item.get("enabled", True)
        upstreams = _normalize_upstreams(item.get("upstreams", []))
        routes.append(RouteSpec(name=name, domain=domain, enabled=bool(enabled), upstreams=upstreams))
    return routes


def _route_specs_from_state(state: StateConfig) -> list[RouteSpec]:
    routes: list[RouteSpec] = []
    default_domain = state.system_domain
    for name, route in state.routes.items():
        if not isinstance(route, dict):
            continue
        routes.append(route_spec_from_dict(name, route, default_domain))
    return routes


def _route_specs_from_config(config: Config) -> list[RouteSpec]:
    routes: list[RouteSpec] = []
    domain = config.get_domain()
    data = config.load()
    for name, value in data.items():
        upstreams = _normalize_upstreams(value)
        routes.append(RouteSpec(name=str(name), domain=domain, enabled=True, upstreams=upstreams))
    return routes


def route_spec_from_dict(name: str, route: dict, default_domain: str) -> RouteSpec:
    domain = str(route.get("domain", default_domain)).strip() or default_domain
    enabled = route.get("enabled", True)
    upstreams = _normalize_upstreams(route.get("upstreams", route.get("upstream")))
    return RouteSpec(name=str(name), domain=domain, enabled=bool(enabled), upstreams=upstreams)


def get_route_specs(state: StateConfig, use_lock: bool = False, lock_path: Path | None = None) -> list[RouteSpec]:
    if use_lock:
        lock = _load_lockfile(lock_path)
        if lock:
            return _route_specs_from_lock(lock)
    routes = _route_specs_from_state(state)
    if routes:
        return routes
    return _route_specs_from_config(Config())


# ─────────────────────────────────────────────────────────────────────────────
# Snippet Generation
# ─────────────────────────────────────────────────────────────────────────────


def _caddy_upstream(upstream: UpstreamSpec) -> str | None:
    if upstream.type == "unix":
        return f"unix//{upstream.target}"
    if upstream.type in {"tcp", "lan", "docker"}:
        parsed = _split_tcp_target(upstream.target)
        if not parsed:
            return None
        scheme, host, port = parsed
        prefix = "https://" if scheme == "https" else "http://"
        return f"{prefix}{host}:{port}"
    return None


def _generate_caddy_snippet(routes: list[RouteSpec]) -> str:
    """Generate Caddy config snippet for all routes (deterministic)."""
    active_routes = [route for route in routes if route.enabled]

    lines = [
        "# Auto-generated by Devhost - do not edit",
        f"# Routes: {len(active_routes)} active",
        "",
    ]

    for route in sorted(active_routes, key=_route_sort_key):
        host = f"{route.name}.{route.domain}"
        upstreams = [_caddy_upstream(u) for u in route.upstreams]
        upstreams = [u for u in upstreams if u]
        lines.append(f"{host} {{")
        lines.append("    bind 127.0.0.1")
        if upstreams:
            lines.append(f"    reverse_proxy {' '.join(upstreams)}")
        else:
            lines.append("    # No valid upstreams configured")
        lines.append("}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _nginx_upstream_name(route: RouteSpec) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", f"{route.name}_{route.domain}")
    return f"devhost_{safe}"


def _generate_nginx_snippet(routes: list[RouteSpec]) -> str:
    """Generate nginx config snippet for all routes (deterministic)."""
    active_routes = [route for route in routes if route.enabled]

    lines = [
        "# Auto-generated by Devhost - do not edit",
        f"# Include in nginx.conf: include {Path.home()}/.devhost/proxy/nginx/devhost.conf;",
        "",
    ]

    for route in sorted(active_routes, key=_route_sort_key):
        host = f"{route.name}.{route.domain}"
        upstreams = []
        schemes = set()
        for upstream in route.upstreams:
            if upstream.type == "unix":
                upstreams.append(f"server unix:{upstream.target};")
                schemes.add("http")
                continue
            if upstream.type in {"tcp", "lan", "docker"}:
                parsed = _split_tcp_target(upstream.target)
                if not parsed:
                    continue
                scheme, host_name, port = parsed
                schemes.add(scheme)
                upstreams.append(f"server {host_name}:{port};")

        if not upstreams:
            lines.extend(
                [
                    "server {",
                    "    listen 127.0.0.1:80;",
                    f"    server_name {host};",
                    "    location / {",
                    "        return 502;",
                    "    }",
                    "}",
                    "",
                ]
            )
            continue

        upstream_name = _nginx_upstream_name(route)
        lines.append(f"upstream {upstream_name} {{")
        lines.extend([f"    {line}" for line in upstreams])
        lines.append("}")
        lines.append("")

        scheme = "https" if "https" in schemes else "http"
        lines.extend(
            [
                "server {",
                "    listen 127.0.0.1:80;",
                f"    server_name {host};",
                "    location / {",
                f"        proxy_pass {scheme}://{upstream_name};",
                "        proxy_http_version 1.1;",
                "        proxy_set_header Host $host;",
                "        proxy_set_header X-Real-IP $remote_addr;",
                "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
                "        proxy_set_header X-Forwarded-Proto $scheme;",
                "    }",
                "}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def _traefik_service_name(route: RouteSpec) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", route.name)
    return f"{safe}-service"


def _generate_traefik_snippet(routes: list[RouteSpec]) -> str:
    """Generate Traefik config snippet (YAML format, deterministic)."""
    active_routes = [route for route in routes if route.enabled]

    lines = [
        "# Auto-generated by Devhost - do not edit",
        "# Add to traefik.yml: providers.file.filename: ~/.devhost/proxy/traefik/devhost.yml",
        "# Note: bind Traefik entrypoints to 127.0.0.1 for localhost-only access.",
        "",
        "http:",
        "  routers:",
    ]

    for route in sorted(active_routes, key=_route_sort_key):
        host = f"{route.name}.{route.domain}"
        service_name = _traefik_service_name(route)
        lines.extend(
            [
                f"    {route.name}:",
                f'      rule: "Host(`{host}`)"',
                f"      service: {service_name}",
            ]
        )

    lines.extend(
        [
            "",
            "  services:",
        ]
    )

    for route in sorted(active_routes, key=_route_sort_key):
        service_name = _traefik_service_name(route)
        lines.append(f"    {service_name}:")
        lines.append("      loadBalancer:")
        lines.append("        servers:")
        for upstream in route.upstreams:
            if upstream.type == "unix":
                url = f"unix://{upstream.target}"
            elif upstream.type in {"tcp", "lan", "docker"}:
                parsed = _split_tcp_target(upstream.target)
                if not parsed:
                    continue
                scheme, host_name, port = parsed
                url = f"{scheme}://{host_name}:{port}"
            else:
                continue
            lines.append(f'          - url: "{url}"')

    return "\n".join(lines).rstrip() + "\n"


def generate_snippet(driver: ProxyDriver, routes: list[RouteSpec]) -> str:
    """Generate proxy config snippet for the specified driver."""
    generators = {
        "caddy": _generate_caddy_snippet,
        "nginx": _generate_nginx_snippet,
        "traefik": _generate_traefik_snippet,
    }
    generator = generators.get(driver)
    if not generator:
        raise ValueError(f"Unsupported proxy driver: {driver}")
    return generator(routes)


def export_snippets(
    state: StateConfig,
    drivers: list[ProxyDriver] | None = None,
    use_lock: bool = False,
    lock_path: Path | None = None,
) -> dict[str, Path]:
    """
    Export snippets for specified drivers (or all if None).

    Returns dict of driver -> exported file path.
    """
    if drivers is None:
        drivers = ["caddy", "nginx", "traefik"]

    routes = get_route_specs(state, use_lock=use_lock, lock_path=lock_path)
    exported = {}

    extensions = {"caddy": "caddy", "nginx": "conf", "traefik": "yml"}

    for driver in drivers:
        ext = extensions.get(driver, "conf")
        snippet_path = state.devhost_dir / "proxy" / driver / f"devhost.{ext}"
        snippet_path.parent.mkdir(parents=True, exist_ok=True)

        content = generate_snippet(driver, routes)
        tmp_path = snippet_path.with_suffix(snippet_path.suffix + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(snippet_path)

        manifest_path = snippet_path.with_suffix(snippet_path.suffix + ".manifest.json")
        manifest = {
            "version": 1,
            "driver": driver,
            "generated_by": {"version": __version__},
            "domain": state.system_domain,
            "routes_hash": _routes_hash(routes),
            "snippet_hash": _snippet_hash(content),
            "snippet_path": str(snippet_path),
            "lockfile_path": str(lock_path) if lock_path else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        # Record hash for integrity tracking
        state.record_hash(snippet_path)
        exported[driver] = snippet_path

    return exported


# ─────────────────────────────────────────────────────────────────────────────
# Proxy Discovery
# ─────────────────────────────────────────────────────────────────────────────


def _get_search_paths(driver: ProxyDriver) -> list[Path]:
    """Get search paths for a proxy driver's config file."""
    home = Path.home()
    cwd = Path.cwd()

    paths = {
        "caddy": [
            cwd / "Caddyfile",
            cwd / "caddy" / "Caddyfile",
            home / ".config" / "caddy" / "Caddyfile",
            Path("/etc/caddy/Caddyfile"),
            # Windows paths
            Path("C:/ProgramData/caddy/Caddyfile"),
        ],
        "nginx": [
            cwd / "nginx.conf",
            cwd / "nginx" / "nginx.conf",
            home / ".config" / "nginx" / "nginx.conf",
            Path("/etc/nginx/nginx.conf"),
            Path("/usr/local/etc/nginx/nginx.conf"),
            # Windows paths
            Path("C:/nginx/conf/nginx.conf"),
        ],
        "traefik": [
            cwd / "traefik.yml",
            cwd / "traefik.yaml",
            cwd / "traefik" / "traefik.yml",
            home / ".config" / "traefik" / "traefik.yml",
            Path("/etc/traefik/traefik.yml"),
        ],
    }
    return paths.get(driver, [])


def discover_proxy_config(driver: ProxyDriver | None = None) -> list[tuple[ProxyDriver, Path]]:
    """
    Discover proxy config files on the system.

    If driver is specified, only search for that driver.
    Returns list of (driver, path) tuples for found configs.
    """
    drivers_to_check: list[ProxyDriver] = [driver] if driver else ["caddy", "nginx", "traefik"]
    found = []

    for drv in drivers_to_check:
        for path in _get_search_paths(drv):
            if path.exists():
                found.append((drv, path))

    return found


def print_discovery_results(results: list[tuple[ProxyDriver, Path]]):
    """Print discovered proxy configs in a formatted way."""
    if not results:
        print_warning("No proxy configurations found.")
        print_info("\nSearched locations include:")
        console.print("  - ./Caddyfile, ./nginx.conf, ./traefik.yml")
        console.print("  - ~/.config/{caddy,nginx,traefik}/")
        console.print("  - /etc/{caddy,nginx,traefik}/")
        return

    print_success(f"Found {len(results)} proxy configuration(s):")
    for i, (driver, path) in enumerate(results, 1):
        console.print(f"  [{i}] {driver}: [cyan]{path}[/cyan]")


# ─────────────────────────────────────────────────────────────────────────────
# Attach / Detach
# ─────────────────────────────────────────────────────────────────────────────


def _get_import_line(driver: ProxyDriver, snippet_path: Path) -> str:
    """Get the import/include line for a driver."""
    abs_path = str(snippet_path.resolve())

    imports = {
        "caddy": f"import {abs_path}",
        "nginx": f"include {abs_path};",
        "traefik": f"# File provider: {abs_path}",  # Traefik uses file provider in main config
    }
    return imports.get(driver, f"# include {abs_path}")


def _create_marker_block(driver: ProxyDriver, snippet_path: Path) -> str:
    """Create the marker block to insert into user config."""
    import_line = _get_import_line(driver, snippet_path)
    return f"{MARKER_BEGIN}\n{import_line}\n{MARKER_END}"


def _manifest_path(snippet_path: Path) -> Path:
    return snippet_path.with_suffix(snippet_path.suffix + ".manifest.json")


def _load_manifest(snippet_path: Path) -> dict | None:
    path = _manifest_path(snippet_path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_manifest(snippet_path: Path, manifest: dict) -> None:
    path = _manifest_path(snippet_path)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def has_marker_block(content: str) -> bool:
    """Check if content already has a devhost marker block."""
    return MARKER_BEGIN in content and MARKER_END in content


def extract_marker_block(content: str) -> str | None:
    """Extract the marker block from content if present."""
    if MARKER_BEGIN not in content or MARKER_END not in content:
        return None

    start = content.find(MARKER_BEGIN)
    end = content.find(MARKER_END) + len(MARKER_END)
    return content[start:end]


def attach_to_config(
    state: StateConfig,
    config_path: Path,
    driver: ProxyDriver,
    *,
    validate: bool = True,
    use_lock: bool = False,
    lock_path: Path | None = None,
) -> tuple[bool, str]:
    """
    Attach devhost snippet import to a proxy config file.

    Returns (success, message).
    """
    if not config_path.exists():
        return (False, f"Config file not found: {config_path}")

    # Read current content
    content = config_path.read_text(encoding="utf-8")

    # Check if already attached
    if has_marker_block(content):
        return (False, "Devhost marker block already exists. Use 'detach' first to re-attach.")

    # Backup the file
    backup_path = state.backup_file(config_path)
    if backup_path:
        print_info(f"Backup created: {backup_path}")
    else:
        print_warning("Could not create backup (file may not exist or permission denied)")

    # Generate snippet first
    snippet_path = state.devhost_dir / "proxy" / driver / f"devhost.{_get_extension(driver)}"
    if not snippet_path.exists():
        # Export snippet if it doesn't exist
        export_snippets(state, [driver], use_lock=use_lock, lock_path=lock_path)

    # Create and insert marker block
    marker_block = _create_marker_block(driver, snippet_path)

    lines = content.split("\n")

    def _strip_nginx_comment(line: str) -> str:
        if "#" in line:
            return line.split("#", 1)[0]
        return line

    def _indent_block(block: str, indent: str) -> list[str]:
        return [f"{indent}{line}" if line else line for line in block.splitlines()]

    def _find_nginx_http_insert(lines_in: list[str]) -> tuple[int, str] | None:
        depth = 0
        for idx, raw in enumerate(lines_in):
            no_comment = _strip_nginx_comment(raw)
            stripped = no_comment.strip()

            if depth == 0:
                if re.match(r"^http\b\s*\{", stripped):
                    indent = re.match(r"^(\s*)", raw).group(1) + "    "
                    return (idx + 1, indent)
                if stripped == "http":
                    for j in range(idx + 1, len(lines_in)):
                        next_raw = lines_in[j]
                        next_stripped = _strip_nginx_comment(next_raw).strip()
                        if not next_stripped:
                            continue
                        if next_stripped.startswith("{"):
                            indent = re.match(r"^(\s*)", next_raw).group(1) + "    "
                            return (j + 1, indent)
                        break

            depth += no_comment.count("{") - no_comment.count("}")

        return None

    if driver == "nginx":
        nginx_insert = _find_nginx_http_insert(lines)
        if nginx_insert:
            insert_idx, indent = nginx_insert
            marker_lines = _indent_block(marker_block, indent)
            lines[insert_idx:insert_idx] = ["", *marker_lines, ""]
        else:
            # Assume conf.d-style file already included within http context
            insert_idx = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and not stripped.startswith("//"):
                    insert_idx = i
                    break
                insert_idx = i + 1
            lines[insert_idx:insert_idx] = ["", marker_block, ""]
    else:
        # Insert at the beginning of the file (after any initial comments)
        insert_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("//"):
                insert_idx = i
                break
            insert_idx = i + 1

        lines.insert(insert_idx, "")
        lines.insert(insert_idx + 1, marker_block)
        lines.insert(insert_idx + 2, "")

    new_content = "\n".join(lines)
    tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    tmp_path.replace(config_path)

    # Record hash for drift detection
    state.record_hash(config_path)

    # Update state with external config
    state.set_external_config(driver, str(config_path))

    manifest = _load_manifest(snippet_path) or {
        "version": 1,
        "driver": driver,
        "generated_by": {"version": __version__},
        "snippet_path": str(snippet_path),
        "snippet_hash": _snippet_hash(snippet_path.read_text(encoding="utf-8")),
    }
    manifest["attach"] = {
        "config_path": str(config_path),
        "marker_block": marker_block,
        "marker_hash": hashlib.sha256(marker_block.encode("utf-8")).hexdigest(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_manifest(snippet_path, manifest)

    if validate:
        ok, msg = validate_proxy_config(driver, config_path)
        if not ok:
            if backup_path and backup_path.exists():
                backup_content = backup_path.read_text(encoding="utf-8", errors="replace")
                config_path.write_text(backup_content, encoding="utf-8")
                state.record_hash(config_path)
            return (False, f"Attach failed validation: {msg}")

    return (True, f"Attached devhost to {config_path}")


def detach_from_config(state: StateConfig, config_path: Path, *, force: bool = False) -> tuple[bool, str]:
    """
    Remove devhost marker block from a proxy config file.

    Returns (success, message).
    """
    if not config_path.exists():
        return (False, f"Config file not found: {config_path}")

    content = config_path.read_text(encoding="utf-8")

    if not has_marker_block(content):
        return (False, "No devhost marker block found in config")

    snippet_path = (
        state.devhost_dir / "proxy" / state.external_driver / f"devhost.{_get_extension(state.external_driver)}"
    )
    manifest = _load_manifest(snippet_path) if snippet_path.exists() else None
    expected_block = None
    if manifest and manifest.get("attach", {}).get("marker_block"):
        expected_block = manifest["attach"]["marker_block"]

    # Check for drift before detaching
    ok, status = state.check_hash(config_path)
    if not ok and status == "modified":
        print_warning("Config file has been modified since last attach.")
        print_warning("The marker block may have been changed. Proceeding with caution.")
        if expected_block and not force:
            return (False, "Marker block drift detected. Use --force to detach anyway.")

    # Backup before detaching
    backup_path = state.backup_file(config_path)
    if backup_path:
        print_info(f"Backup created: {backup_path}")

    # Remove marker block
    if expected_block and expected_block in content:
        start = content.find(expected_block)
        end = start + len(expected_block)
    else:
        start = content.find(MARKER_BEGIN)
        end = content.find(MARKER_END) + len(MARKER_END)
        if start < 0 or end <= start:
            return (False, "Marker block not found in config.")

    # Also remove surrounding blank lines
    before = content[:start].rstrip("\n")
    after = content[end:].lstrip("\n")

    new_content = before + "\n\n" + after if before else after

    tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    tmp_path.replace(config_path)

    # Record hash for drift detection
    state.record_hash(config_path)

    if manifest and "attach" in manifest:
        manifest.pop("attach", None)
        _write_manifest(snippet_path, manifest)

    return (True, f"Detached devhost from {config_path}")


def _get_extension(driver: ProxyDriver) -> str:
    """Get file extension for a driver."""
    return {"caddy": "caddy", "nginx": "conf", "traefik": "yml"}.get(driver, "conf")


def validate_proxy_config(driver: ProxyDriver, config_path: Path) -> tuple[bool, str]:
    """Validate proxy config using native validators when available."""
    if not config_path.exists():
        return (False, f"Config file not found: {config_path}")

    def _run(cmd: list[str]) -> tuple[bool, str]:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        output = (result.stdout + result.stderr).strip()
        return (result.returncode == 0, output or "validation failed")

    if driver == "nginx":
        if not shutil.which("nginx"):
            return (False, "nginx not found in PATH")
        return _run(["nginx", "-t", "-c", str(config_path)])

    if driver == "caddy":
        if not shutil.which("caddy"):
            return (False, "caddy not found in PATH")
        return _run(["caddy", "validate", "--config", str(config_path)])

    if driver == "traefik":
        if shutil.which("traefik"):
            return _run(["traefik", "check", "--configFile", str(config_path)])
        try:
            import yaml

            yaml.safe_load(config_path.read_text(encoding="utf-8"))
            return (True, "YAML parsed successfully (traefik binary not found)")
        except Exception as exc:
            return (False, f"Traefik config parse failed: {exc}")

    return (False, f"Unsupported proxy driver: {driver}")


def write_lockfile(state: StateConfig, path: Path | None = None) -> Path:
    """Write a deterministic proxy lockfile for team reproducibility."""
    lock_path = path or _lockfile_path()
    routes = get_route_specs(state)
    payload = {
        "version": 1,
        "generated_by": {"version": __version__},
        "domain": state.system_domain,
        "driver": state.external_driver,
        "routes": _routes_payload(routes),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    lock_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return lock_path


def apply_lockfile(
    state: StateConfig,
    path: Path | None = None,
    *,
    update_config: bool = True,
) -> tuple[bool, str]:
    """Apply a proxy lockfile to state (and optionally devhost.json)."""
    lock_path = path or _lockfile_path()
    lock = _load_lockfile(lock_path)
    if not lock:
        return (False, f"Lockfile not found or unreadable: {lock_path}")

    routes = _route_specs_from_lock(lock)
    if not routes:
        return (False, "Lockfile contains no routes.")

    new_state = state.raw
    new_state["routes"] = {}
    for route in routes:
        route_dict: dict = {
            "domain": route.domain,
            "enabled": route.enabled,
            "upstreams": [{"type": u.type, "target": u.target} for u in route.upstreams],
        }
        # Keep legacy upstream field for gateway-compatible targets
        primary = None
        for upstream in route.upstreams:
            if upstream.type in {"tcp", "lan", "docker"}:
                parsed = _split_tcp_target(upstream.target)
                if parsed:
                    scheme, host, port = parsed
                    primary = f"{host}:{port}" if scheme == "http" else f"{scheme}://{host}:{port}"
                    break
        if primary:
            route_dict["upstream"] = primary
        new_state["routes"][route.name] = route_dict

    if lock.get("domain"):
        new_state.setdefault("proxy", {}).setdefault("system", {})["domain"] = lock["domain"]

    state.replace_state(new_state)

    if update_config:
        config = Config()
        config_payload: dict[str, str | int] = {}
        for route in routes:
            value = None
            for upstream in route.upstreams:
                if upstream.type in {"tcp", "lan", "docker"}:
                    parsed = _split_tcp_target(upstream.target)
                    if parsed:
                        scheme, host, port = parsed
                        value = f"{host}:{port}" if scheme == "http" else f"{scheme}://{host}:{port}"
                        break
            if value is not None:
                config_payload[route.name] = value
        config.save(config_payload)

    return (True, f"Applied lockfile: {lock_path}")


def check_proxy_drift(
    state: StateConfig,
    driver: ProxyDriver,
    config_path: Path | None = None,
    *,
    validate: bool = False,
) -> dict:
    """Check for proxy drift and return a structured report."""
    snippet_path = state.devhost_dir / "proxy" / driver / f"devhost.{_get_extension(driver)}"
    manifest = _load_manifest(snippet_path) if snippet_path.exists() else None

    report = {"ok": True, "issues": []}

    if not snippet_path.exists():
        report["issues"].append(
            {"code": "snippet_missing", "message": f"Snippet missing: {snippet_path}", "fix": "Run export."}
        )
    else:
        current = snippet_path.read_text(encoding="utf-8")
        if manifest and manifest.get("snippet_hash"):
            if _snippet_hash(current) != manifest.get("snippet_hash"):
                report["issues"].append(
                    {
                        "code": "snippet_modified",
                        "message": "Snippet contents differ from manifest.",
                        "fix": "Regenerate snippet or accept changes.",
                    }
                )
        elif not manifest:
            report["issues"].append(
                {"code": "manifest_missing", "message": "Manifest missing for snippet.", "fix": "Re-export snippet."}
            )

    if config_path:
        if not config_path.exists():
            report["issues"].append(
                {"code": "config_missing", "message": f"Config missing: {config_path}", "fix": "Fix path or detach."}
            )
        else:
            content = config_path.read_text(encoding="utf-8")
            marker_block = _create_marker_block(driver, snippet_path)
            if marker_block not in content:
                report["issues"].append(
                    {
                        "code": "marker_missing",
                        "message": "Managed include/import block missing.",
                        "fix": "Re-attach or detach cleanly.",
                    }
                )
            import_line = _get_import_line(driver, snippet_path)
            if import_line not in content:
                report["issues"].append(
                    {
                        "code": "import_missing",
                        "message": "Include/import line not found in config.",
                        "fix": "Re-attach or update config.",
                    }
                )

    if validate and config_path:
        ok, msg = validate_proxy_config(driver, config_path)
        if not ok:
            report["issues"].append(
                {"code": "validation_failed", "message": f"Validation failed: {msg}", "fix": "Fix config syntax."}
            )

    report["ok"] = len(report["issues"]) == 0
    return report


def accept_proxy_drift(
    state: StateConfig,
    driver: ProxyDriver,
    config_path: Path | None = None,
) -> tuple[bool, str]:
    """Accept current files as the new baseline in the manifest."""
    snippet_path = state.devhost_dir / "proxy" / driver / f"devhost.{_get_extension(driver)}"
    if not snippet_path.exists():
        return (False, "Snippet file not found.")

    content = snippet_path.read_text(encoding="utf-8")
    manifest = _load_manifest(snippet_path) or {
        "version": 1,
        "driver": driver,
        "generated_by": {"version": __version__},
        "snippet_path": str(snippet_path),
    }
    manifest["snippet_hash"] = _snippet_hash(content)
    manifest["routes_hash"] = manifest.get("routes_hash") or _routes_hash(get_route_specs(state))
    if config_path:
        marker_block = _create_marker_block(driver, snippet_path)
        manifest["attach"] = {
            "config_path": str(config_path),
            "marker_block": marker_block,
            "marker_hash": hashlib.sha256(marker_block.encode("utf-8")).hexdigest(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        state.record_hash(config_path)
    _write_manifest(snippet_path, manifest)
    return (True, "Accepted current files as new baseline.")


def sync_proxy(
    state: StateConfig,
    driver: ProxyDriver,
    *,
    watch: bool = False,
    interval: float = 2.0,
    use_lock: bool = False,
    lock_path: Path | None = None,
) -> None:
    """Sync proxy snippets, optionally watching for route changes."""
    last_hash = None
    while True:
        routes = get_route_specs(state, use_lock=use_lock, lock_path=lock_path)
        current_hash = _routes_hash(routes)
        if current_hash != last_hash:
            export_snippets(state, [driver], use_lock=use_lock, lock_path=lock_path)
            last_hash = current_hash
        if not watch:
            return
        time.sleep(interval)


# ─────────────────────────────────────────────────────────────────────────────
# Transfer (Mode 2 -> Mode 3)
# ─────────────────────────────────────────────────────────────────────────────


def verify_route(host: str, port: int = 80, timeout: float = 2.0) -> tuple[bool, str]:
    """
    Verify a route is accessible through the proxy.

    Sends a request with Host header and checks for non-error response.
    Returns (success, message).
    """
    try:
        url = f"http://127.0.0.1:{port}/"
        response = httpx.get(url, headers={"Host": host}, timeout=timeout, follow_redirects=False)

        # Accept any 2xx, 3xx, or even some 4xx (like 401/403 which indicate routing works)
        if response.status_code < 500:
            return (True, f"OK ({response.status_code})")
        return (False, f"Server error ({response.status_code})")
    except httpx.ConnectError:
        return (False, "Connection refused")
    except httpx.TimeoutException:
        return (False, "Timeout")
    except Exception as e:
        return (False, str(e))


def verify_all_routes(
    state: StateConfig,
    port: int = 80,
) -> dict[str, tuple[bool, str]]:
    """
    Verify all routes through the external proxy.

    Returns dict of route_name -> (success, message).
    """
    results = {}
    domain = state.system_domain

    for name, route in state.routes.items():
        if not route.get("enabled", True):
            results[name] = (True, "Disabled (skipped)")
            continue

        route_domain = route.get("domain", domain)
        host = f"{name}.{route_domain}"
        results[name] = verify_route(host, port)

    return results


def transfer_to_external(
    state: StateConfig,
    driver: ProxyDriver,
    config_path: Path | None = None,
    auto_attach: bool = True,
    verify: bool = True,
    port: int = 80,
) -> tuple[bool, str]:
    """
    Transfer from Mode 2 (system) to Mode 3 (external).

    Steps:
    1. Generate snippets for all routes
    2. Optionally attach into external proxy config
    3. Verify routes if requested
    4. Switch proxy mode to external

    Returns (success, message).
    """
    print_info("Starting transfer to external proxy mode...")

    # Step 1: Generate snippets
    print_info("Generating proxy snippets...")
    exported = export_snippets(state, [driver])
    snippet_path = exported.get(driver)
    if snippet_path:
        print_success(f"Snippet exported: {snippet_path}")

    # Step 2: Attach if requested
    if auto_attach:
        if config_path is None:
            # Try to discover
            found = discover_proxy_config(driver)
            if not found:
                return (False, f"No {driver} config found. Specify --config-path or run 'proxy attach' manually.")
            config_path = found[0][1]
            print_info(f"Using discovered config: {config_path}")

        success, msg = attach_to_config(state, config_path, driver)
        if not success:
            return (False, f"Attach failed: {msg}")
        print_success(msg)
    else:
        # Persist external driver/config even when attach is skipped
        if config_path is not None:
            state.set_external_config(driver, str(config_path))
        else:
            state.set_external_config(driver)

    # Step 3: Verify routes
    if verify:
        print_info("Verifying routes through external proxy...")
        results = verify_all_routes(state, port)

        all_ok = True
        for name, (ok, status) in results.items():
            if ok:
                print_success(f"  {name}: {status}")
            else:
                print_error(f"  {name}: {status}")
                all_ok = False

        if not all_ok:
            print_warning("\nSome routes failed verification.")
            print_warning("The external proxy may need to be reloaded.")
            print_warning("Transfer aborted. Fix issues and try again.")
            return (False, "Route verification failed")

    # Step 4: Switch mode
    state.proxy_mode = "external"
    print_success(f"Proxy mode switched to: external ({driver})")

    return (True, "Transfer complete")


# ─────────────────────────────────────────────────────────────────────────────
# CLI Handlers
# ─────────────────────────────────────────────────────────────────────────────


def cmd_proxy_export(
    driver: str | None = None,
    show: bool = False,
    *,
    use_lock: bool = False,
    lock_path: Path | None = None,
):
    """Handle 'devhost proxy export' command."""
    state = StateConfig()

    if state.route_count() == 0:
        print_warning("No routes configured. Add some routes first with 'devhost add'.")
        return

    drivers: list[ProxyDriver] = [driver] if driver else ["caddy", "nginx", "traefik"]

    if show:
        # Just print the snippet without saving
        for drv in drivers:
            routes = get_route_specs(state, use_lock=use_lock, lock_path=lock_path)
            content = generate_snippet(drv, routes)
            console.print(f"\n[bold cyan]─── {drv.upper()} ───[/bold cyan]")
            console.print(content)
        return

    exported = export_snippets(state, drivers, use_lock=use_lock, lock_path=lock_path)
    print_success("Exported proxy snippets:")
    for drv, path in exported.items():
        console.print(f"  {drv}: [cyan]{path}[/cyan]")

    print_info("\nNext steps:")
    console.print("  1. Review the generated snippets")
    console.print("  2. Run 'devhost proxy attach' to add to your proxy config")
    console.print("  3. Or manually include the snippet in your proxy config")


def cmd_proxy_discover():
    """Handle 'devhost proxy discover' command."""
    results = discover_proxy_config()
    print_discovery_results(results)


def cmd_proxy_attach(driver: str, config_path: str | None = None):
    """Handle 'devhost proxy attach' command."""
    state = StateConfig()

    if config_path:
        path = Path(config_path)
    else:
        # Try to discover
        found = discover_proxy_config(driver)
        if not found:
            print_error(f"No {driver} config found. Specify --config-path.")
            return
        if len(found) > 1:
            print_warning("Multiple configs found. Specify --config-path:")
            for drv, p in found:
                console.print(f"  {drv}: {p}")
            return
        path = found[0][1]

    success, msg = attach_to_config(state, path, driver)
    if success:
        print_success(msg)
        print_info("\nRemember to reload your proxy to apply changes.")
    else:
        print_error(msg)


def cmd_proxy_detach(config_path: str | None = None):
    """Handle 'devhost proxy detach' command."""
    state = StateConfig()

    if config_path:
        path = Path(config_path)
    else:
        # Use configured path
        path = state.external_config_path
        if not path:
            print_error("No external config path configured. Specify --config-path.")
            return

    success, msg = detach_from_config(state, path)
    if success:
        print_success(msg)
    else:
        print_error(msg)


def cmd_proxy_transfer(
    driver: str,
    config_path: str | None = None,
    no_attach: bool = False,
    no_verify: bool = False,
    port: int = 80,
):
    """Handle 'devhost proxy transfer' command."""
    state = StateConfig()

    if state.route_count() == 0:
        print_warning("No routes configured. Add some routes first with 'devhost add'.")
        return

    path = Path(config_path) if config_path else None
    success, msg = transfer_to_external(
        state,
        driver,
        config_path=path,
        auto_attach=not no_attach,
        verify=not no_verify,
        port=port,
    )

    if success:
        print_success(msg)
    else:
        print_error(msg)
