"""
Unified state management for Devhost CLI.

Manages ~/.devhost/state.yml with:
- Proxy mode configuration (off/gateway/system/external)
- Route definitions
- Integrity hashing for drift detection
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

ProxyMode = Literal["off", "gateway", "system", "external"]

# Default state schema
DEFAULT_STATE: dict[str, Any] = {
    "version": 3,
    "proxy": {
        "mode": "gateway",  # off|gateway|system|external
        "gateway": {
            "listen": "127.0.0.1:7777",
        },
        "system": {
            "owned": True,
            "domain": "localhost",
            "listen_http": "127.0.0.1:80",
            "listen_https": "127.0.0.1:443",
            "caddy_pid": None,
        },
        "external": {
            "driver": "caddy",  # caddy|nginx|traefik
            "config_path": None,
            "snippet_path": None,
            "attach": {"auto_import": False},
            "reload": {"mode": "manual", "command": None},
        },
    },
    "integrity": {
        "enabled": True,
        "hashes": {},
    },
    "routes": {},
}


def parse_listen(value: str | None, default_host: str, default_port: int) -> tuple[str, int]:
    """Parse a listen address into (host, port)."""
    if not value:
        return (default_host, default_port)
    text = str(value).strip()
    if not text:
        return (default_host, default_port)
    if text.startswith("[") and "]" in text:
        host, _, remainder = text[1:].partition("]")
        if remainder.startswith(":") and remainder[1:].isdigit():
            return (host or default_host, int(remainder[1:]))
        return (host or default_host, default_port)
    if ":" in text:
        host, port_str = text.rsplit(":", 1)
        if port_str.isdigit():
            return (host or default_host, int(port_str))
        return (host or default_host, default_port)
    return (text, default_port)


def get_devhost_dir() -> Path:
    """Get the ~/.devhost directory path"""
    return Path.home() / ".devhost"


def get_state_file() -> Path:
    """Get the state.yml file path"""
    return get_devhost_dir() / "state.yml"


def compute_file_hash(filepath: Path) -> str | None:
    """Compute SHA-256 hash of a file"""
    if not filepath.exists():
        return None
    try:
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return f"sha256:{hasher.hexdigest()}"
    except OSError:
        return None


class StateConfig:
    """
    Manages the unified ~/.devhost/state.yml configuration.

    This is the single source of truth for:
    - Current proxy mode
    - Route definitions
    - File integrity hashes
    """

    def __init__(self):
        self.devhost_dir = get_devhost_dir()
        self.state_file = get_state_file()
        self._state: dict[str, Any] = {}
        self._load()

    def _ensure_dirs(self):
        """Ensure all required directories exist"""
        dirs = [
            self.devhost_dir,
            self.devhost_dir / "backups",
            self.devhost_dir / "proxy" / "caddy",
            self.devhost_dir / "proxy" / "nginx",
            self.devhost_dir / "proxy" / "traefik",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def _load(self):
        """Load state from file or create default"""
        self._ensure_dirs()

        if self.state_file.exists():
            try:
                with open(self.state_file, encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                    if isinstance(loaded, dict):
                        self._state = self._merge_defaults(loaded)
                    else:
                        self._state = DEFAULT_STATE.copy()
            except (OSError, yaml.YAMLError):
                self._state = DEFAULT_STATE.copy()
        else:
            self._state = DEFAULT_STATE.copy()
            self._save()

    def _merge_defaults(self, loaded: dict) -> dict:
        """Deep merge loaded config with defaults"""
        result = DEFAULT_STATE.copy()

        def deep_merge(base: dict, overlay: dict) -> dict:
            merged = base.copy()
            for key, value in overlay.items():
                if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                    merged[key] = deep_merge(merged[key], value)
                else:
                    merged[key] = value
            return merged

        return deep_merge(result, loaded)

    def _save(self):
        """Save state to file with secure permissions"""
        import stat
        import sys
        
        self._ensure_dirs()
        try:
            # Write atomically
            tmp = self.state_file.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                yaml.dump(self._state, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            
            # Set restrictive permissions before replacing (Unix only)
            if sys.platform != "win32":
                tmp.chmod(0o600)  # Owner read/write only
            
            tmp.replace(self.state_file)
            
            # Ensure final file also has restrictive permissions (Unix only)
            if sys.platform != "win32":
                self.state_file.chmod(0o600)
        except OSError as e:
            raise RuntimeError(f"Failed to save state: {e}") from e

    # ─────────────────────────────────────────────────────────────
    # Proxy Mode
    # ─────────────────────────────────────────────────────────────

    @property
    def proxy_mode(self) -> ProxyMode:
        """Get current proxy mode"""
        mode = self._state.get("proxy", {}).get("mode", "gateway")
        if mode in ("off", "gateway", "system", "external"):
            return mode
        return "gateway"

    @proxy_mode.setter
    def proxy_mode(self, value: ProxyMode):
        """Set proxy mode"""
        if value not in ("off", "gateway", "system", "external"):
            raise ValueError(f"Invalid proxy mode: {value}")
        self._state.setdefault("proxy", {})["mode"] = value
        self._save()

    @property
    def gateway_listen(self) -> str:
        """Get gateway listen address"""
        return self._state.get("proxy", {}).get("gateway", {}).get("listen", "127.0.0.1:7777")

    @property
    def gateway_port(self) -> int:
        """Get gateway port number"""
        listen = self.gateway_listen
        if ":" in listen:
            return int(listen.split(":")[-1])
        return 7777

    def set_gateway_listen(self, host: str, port: int | None = None) -> None:
        """Set gateway listen address."""
        host = (host or "").strip()
        if not host or any(c in host for c in ("\r", "\n", "\x00")):
            raise ValueError("Invalid gateway listen host")
        _, current_port = parse_listen(self.gateway_listen, "127.0.0.1", 7777)
        port = current_port if port is None else port
        if not (1 <= int(port) <= 65535):
            raise ValueError("Invalid gateway listen port")
        self._state.setdefault("proxy", {}).setdefault("gateway", {})["listen"] = f"{host}:{int(port)}"
        self._save()

    def set_system_listen(self, host: str, http_port: int | None = None, https_port: int | None = None) -> None:
        """Set system proxy listen addresses (HTTP/HTTPS)."""
        host = (host or "").strip()
        if not host or any(c in host for c in ("\r", "\n", "\x00")):
            raise ValueError("Invalid system listen host")
        system = self._state.setdefault("proxy", {}).setdefault("system", {})
        current_http = system.get("listen_http", "127.0.0.1:80")
        current_https = system.get("listen_https", "127.0.0.1:443")
        _, current_http_port = parse_listen(current_http, "127.0.0.1", 80)
        _, current_https_port = parse_listen(current_https, "127.0.0.1", 443)
        http_port = current_http_port if http_port is None else http_port
        https_port = current_https_port if https_port is None else https_port
        if not (1 <= int(http_port) <= 65535):
            raise ValueError("Invalid system HTTP listen port")
        if not (1 <= int(https_port) <= 65535):
            raise ValueError("Invalid system HTTPS listen port")
        system["listen_http"] = f"{host}:{int(http_port)}"
        system["listen_https"] = f"{host}:{int(https_port)}"
        self._save()

    @property
    def system_domain(self) -> str:
        """Get system proxy domain"""
        return self._state.get("proxy", {}).get("system", {}).get("domain", "localhost")

    @system_domain.setter
    def system_domain(self, value: str) -> None:
        """Set system proxy domain"""
        old_domain = self.system_domain
        domain = (value or "").strip().lower()
        if not domain:
            raise ValueError("Domain cannot be empty")
        if "/" in domain or domain.startswith("http"):
            raise ValueError("Domain must be a hostname only (no scheme or path)")
        self._state.setdefault("proxy", {}).setdefault("system", {})["domain"] = domain

        # Keep route domains consistent when they were previously using the old global domain.
        routes = self._state.get("routes", {})
        if isinstance(routes, dict):
            for route in routes.values():
                if isinstance(route, dict) and route.get("domain") == old_domain:
                    route["domain"] = domain

        self._save()

    # ─────────────────────────────────────────────────────────────
    # Routes
    # ─────────────────────────────────────────────────────────────

    @property
    def routes(self) -> dict[str, dict]:
        """Get all routes"""
        return self._state.get("routes", {})

    def get_route(self, name: str) -> dict | None:
        """Get a single route by name"""
        return self.routes.get(name)

    def set_route(
        self,
        name: str,
        upstream: str,
        domain: str = "localhost",
        enabled: bool = True,
        tags: list | None = None,
        upstreams: list[dict] | None = None,
    ):
        """Add or update a route"""
        route = {
            "upstream": upstream,
            "domain": domain,
            "enabled": enabled,
            "tags": tags or [],
        }
        if upstreams:
            route["upstreams"] = upstreams
        self._state.setdefault("routes", {})[name] = route
        self._save()

    def remove_route(self, name: str) -> bool:
        """Remove a route"""
        if name in self._state.get("routes", {}):
            del self._state["routes"][name]
            self._save()
            return True
        return False

    def route_count(self) -> int:
        """Get number of routes"""
        return len(self.routes)

    # ─────────────────────────────────────────────────────────────
    # Integrity Hashing
    # ─────────────────────────────────────────────────────────────

    @property
    def integrity_enabled(self) -> bool:
        """Check if integrity tracking is enabled"""
        return self._state.get("integrity", {}).get("enabled", True)

    def record_hash(self, filepath: Path):
        """Record the hash of a file"""
        file_hash = compute_file_hash(filepath)
        if file_hash:
            abs_path = str(filepath.resolve())
            self._state.setdefault("integrity", {}).setdefault("hashes", {})[abs_path] = file_hash
            self._save()

    def remove_hash(self, filepath: Path) -> None:
        """Remove a file from integrity tracking"""
        abs_path = str(filepath.resolve())
        hashes = self._state.setdefault("integrity", {}).setdefault("hashes", {})
        if abs_path in hashes:
            del hashes[abs_path]
            self._save()

    def check_hash(self, filepath: Path) -> tuple[bool, str | None]:
        """
        Check if a file matches its recorded hash.

        Returns:
            (matches: bool, status: str)
            - (True, "ok") - file matches
            - (False, "modified") - file was modified
            - (False, "missing") - file doesn't exist
            - (True, "untracked") - file not in integrity tracking
        """
        abs_path = str(filepath.resolve())
        stored_hash = self._state.get("integrity", {}).get("hashes", {}).get(abs_path)

        if stored_hash is None:
            return (True, "untracked")

        if not filepath.exists():
            return (False, "missing")

        current_hash = compute_file_hash(filepath)
        if current_hash == stored_hash:
            return (True, "ok")
        return (False, "modified")

    def get_all_hashes(self) -> dict[str, str]:
        """Get all recorded file hashes"""
        return self._state.get("integrity", {}).get("hashes", {}).copy()

    def check_all_integrity(self) -> dict[str, tuple[bool, str]]:
        """Check integrity of all tracked files"""
        results = {}
        for filepath_str in self.get_all_hashes():
            filepath = Path(filepath_str)
            results[filepath_str] = self.check_hash(filepath)
        return results

    # ─────────────────────────────────────────────────────────────
    # Backup Management
    # ─────────────────────────────────────────────────────────────

    def backup_file(self, filepath: Path) -> Path | None:
        """Create a backup of a file in ~/.devhost/backups/"""
        if not filepath.exists():
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_name = f"{filepath.name}.{timestamp}.bak"
        backup_path = self.devhost_dir / "backups" / backup_name

        try:
            import shutil

            shutil.copy2(filepath, backup_path)
            return backup_path
        except OSError:
            return None

    # ─────────────────────────────────────────────────────────────
    # External Proxy Configuration
    # ─────────────────────────────────────────────────────────────

    @property
    def external_driver(self) -> str:
        """Get external proxy driver (caddy/nginx/traefik)"""
        return self._state.get("proxy", {}).get("external", {}).get("driver", "caddy")

    @property
    def external_config_path(self) -> Path | None:
        """Get external proxy config path"""
        path = self._state.get("proxy", {}).get("external", {}).get("config_path")
        return Path(path) if path else None

    @property
    def snippet_path(self) -> Path:
        """Get the snippet file path for current driver"""
        driver = self.external_driver
        custom = self._state.get("proxy", {}).get("external", {}).get("snippet_path")
        if custom:
            return Path(custom)

        extensions = {"caddy": "caddy", "nginx": "conf", "traefik": "yml"}
        ext = extensions.get(driver, "conf")
        return self.devhost_dir / "proxy" / driver / f"devhost.{ext}"

    def set_external_config(self, driver: str, config_path: str | None = None):
        """Configure external proxy settings"""
        external = self._state.setdefault("proxy", {}).setdefault("external", {})
        external["driver"] = driver
        if config_path:
            external["config_path"] = str(Path(config_path).resolve())
        self._save()

    # ─────────────────────────────────────────────────────────────
    # Tunnel Management
    # ─────────────────────────────────────────────────────────────

    def get_active_tunnel(self, route_name: str) -> dict | None:
        """Get active tunnel info for a route"""
        return self._state.get("tunnels", {}).get(route_name)

    def get_all_tunnels(self) -> dict[str, dict]:
        """Get all active tunnels"""
        return self._state.get("tunnels", {}).copy()

    def set_tunnel(self, route_name: str, tunnel_info: dict):
        """Record a tunnel for a route"""
        self._state.setdefault("tunnels", {})[route_name] = tunnel_info
        self._save()

    def remove_tunnel(self, route_name: str) -> bool:
        """Remove a tunnel record"""
        if route_name in self._state.get("tunnels", {}):
            del self._state["tunnels"][route_name]
            self._save()
            return True
        return False

    # ─────────────────────────────────────────────────────────────
    # Raw State Access (for advanced use)
    # ─────────────────────────────────────────────────────────────

    @property
    def raw(self) -> dict:
        """Get raw state dict (read-only view)"""
        return self._state.copy()

    def reload(self):
        """Reload state from disk"""
        self._load()

    def replace_state(self, new_state: dict) -> None:
        """Replace state from a raw dict and persist to disk."""
        self._state = self._merge_defaults(new_state)
        self._save()
