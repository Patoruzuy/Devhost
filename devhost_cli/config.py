"""Configuration management for devhost.json, devhost.yml and domain settings"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from .utils import msg_error, msg_success, msg_warning

logger = logging.getLogger("devhost.config")

# Try to import yaml, but don't fail if not installed
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class ProjectConfig:
    """
    Manages per-project devhost.yml configuration.

    Schema:
        name: str           # App name (becomes subdomain)
        port: int           # Port to run on (default: auto)
        domain: str         # Base domain (default: localhost)
        auto_register: bool # Auto-register on startup (default: true)
        auto_caddy: bool    # Auto-start Caddy for port 80 (default: true)
    """

    DEFAULT_CONFIG = {
        "name": None,  # Will be auto-detected from directory
        "port": 0,  # 0 = auto-detect free port
        "domain": "localhost",
        "auto_register": True,
        "auto_caddy": True,
    }

    def __init__(self, start_path: Path | None = None):
        self.start_path = Path(start_path or os.getcwd()).resolve()
        self.config_file: Path | None = None
        self.config: dict = {}
        self._find_and_load()

    def _find_and_load(self):
        """Search for devhost.yml in current and parent directories"""
        current = self.start_path

        # Search up to 10 levels (prevent infinite loop)
        for _ in range(10):
            # Check for yml first, then yaml
            for filename in ["devhost.yml", "devhost.yaml"]:
                config_path = current / filename
                if config_path.exists():
                    self.config_file = config_path
                    self._load_yaml()
                    return

            # Move to parent
            parent = current.parent
            if parent == current:
                break
            current = parent

        # No config found - use defaults
        self.config = self.DEFAULT_CONFIG.copy()
        # Auto-detect name from directory
        self.config["name"] = self.start_path.name.lower().replace(" ", "-")

    def _load_yaml(self):
        """Load config from YAML file"""
        if not YAML_AVAILABLE:
            msg_warning("pyyaml not installed. Run: pip install devhost[yaml]")
            self.config = self.DEFAULT_CONFIG.copy()
            return

        try:
            with open(self.config_file, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            # Merge with defaults
            self.config = {**self.DEFAULT_CONFIG, **data}

            # Auto-detect name if not specified
            if not self.config.get("name"):
                self.config["name"] = self.config_file.parent.name.lower().replace(" ", "-")

        except Exception as e:
            msg_error(f"Failed to load {self.config_file}: {e}")
            self.config = self.DEFAULT_CONFIG.copy()

    def save(self, path: Path | None = None):
        """Save config to YAML file"""
        if not YAML_AVAILABLE:
            msg_error("pyyaml not installed. Run: pip install devhost[yaml]")
            return False

        save_path = path or self.config_file or (self.start_path / "devhost.yml")

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            self.config_file = save_path
            return True
        except Exception as e:
            msg_error(f"Failed to save config: {e}")
            return False

    @property
    def name(self) -> str:
        return self.config.get("name") or self.start_path.name.lower()

    @property
    def port(self) -> int:
        return self.config.get("port") or 0

    @property
    def domain(self) -> str:
        return self.config.get("domain") or "localhost"

    @property
    def auto_register(self) -> bool:
        return self.config.get("auto_register", True)

    @property
    def auto_caddy(self) -> bool:
        return self.config.get("auto_caddy", True)

    @property
    def url(self) -> str:
        """Get the full URL for this app"""
        return f"http://{self.name}.{self.domain}"

    def exists(self) -> bool:
        """Check if a project config file was found"""
        return self.config_file is not None


class Config:
    """Manages devhost.json configuration"""

    def __init__(self):
        env_path = os.getenv("DEVHOST_CONFIG")
        if env_path:
            self.config_file = Path(env_path).expanduser().resolve()
            self.script_dir = self.config_file.parent
            self.domain_file = self.script_dir / ".devhost" / "domain"
        else:
            # Default to user-owned config so pip installs work without writing into site-packages.
            self.script_dir = Path.home() / ".devhost"
            self.config_file = self.script_dir / "devhost.json"
            self.domain_file = self.script_dir / "domain"
            self._migrate_legacy_user_files()

    def _migrate_legacy_user_files(self) -> None:
        """
        Best-effort migration from legacy repo/site-packages locations into ~/.devhost.

        This avoids breaking upgrades where older versions wrote devhost.json or
        .devhost/domain under the package directory.
        """
        try:
            if self.config_file.exists() and self.domain_file.exists():
                return
        except OSError:
            return

        legacy_root = Path(__file__).parent.parent.resolve()
        legacy_config = legacy_root / "devhost.json"
        legacy_domain = legacy_root / ".devhost" / "domain"

        try:
            self.script_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return

        try:
            if (not self.config_file.exists()) and legacy_config.is_file():
                self.config_file.write_text(legacy_config.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            pass

        try:
            if (not self.domain_file.exists()) and legacy_domain.is_file():
                self.domain_file.write_text(legacy_domain.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            pass

    def load(self) -> dict:
        """Load configuration from file"""
        if not self.config_file.exists():
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            self.config_file.write_text("{}", encoding="utf-8")
            return {}

        try:
            with open(self.config_file) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                return {}
        except (OSError, json.JSONDecodeError) as e:
            msg_error(f"Failed to load config: {e}")
            return {}

    def save(self, data: dict):
        """Save configuration to file"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.config_file.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
            tmp.replace(self.config_file)
        except OSError as e:
            msg_error(f"Failed to save config: {e}")
            raise

    def get_domain(self) -> str:
        """Get base domain from env or config"""
        # Check environment variable first
        domain = os.environ.get("DEVHOST_DOMAIN", "").strip()
        if domain:
            return domain

        # Check legacy domain file first (supports per-workspace configs via DEVHOST_CONFIG)
        if self.domain_file.exists():
            try:
                domain = self.domain_file.read_text().strip()
                if domain:
                    return domain
            except OSError:
                pass

        # Prefer unified v3 state as fallback
        try:
            from .state import StateConfig

            domain = StateConfig().system_domain
            if domain:
                return domain
        except Exception:
            pass

        return "localhost"

    def set_domain(self, domain: str) -> bool:
        """Set base domain"""
        if not domain:
            msg_error("Domain cannot be empty")
            return False

        # Validate domain
        if "/" in domain or domain.startswith("http"):
            msg_error("Domain must be a hostname only (no scheme or path)")
            return False

        try:
            self.domain_file.parent.mkdir(parents=True, exist_ok=True)
            self.domain_file.write_text(domain)
            msg_success(f"Domain set to: {domain}")

            # Keep v3 state in sync (mode/system/external tooling relies on it)
            try:
                from .state import StateConfig

                state = StateConfig()
                state.system_domain = domain
            except Exception:
                pass

            # Regenerate Caddyfile with new domain
            from .caddy import generate_caddyfile

            generate_caddyfile(self.load())

            # Update Windows hosts if needed
            from .platform import IS_WINDOWS, is_admin
            from .windows import hosts_sync

            if IS_WINDOWS and domain != "localhost":
                if is_admin():
                    hosts_sync()
                else:
                    msg_warning("Run PowerShell as Administrator to update hosts entries for existing mappings.")

            return True
        except OSError as e:
            msg_error(f"Failed to set domain: {e}")
            return False


def validate_config(
    config_data: dict[str, Any] | None = None, config_file: Path | None = None
) -> tuple[bool, list[str]]:
    """
    Validate devhost.json configuration for correctness and security.

    Checks:
    - Config file exists and is readable
    - JSON structure is valid dict
    - Route names are valid (alphanumeric + hyphens, max 63 chars)
    - Target values are valid (port, host:port, or URL)
    - No duplicate route names
    - File permissions are reasonable (not world-writable)

    Args:
        config_data: Config dict to validate (or None to load from file)
        config_file: Path to config file (or None to use default)

    Returns:
        (is_valid, errors): Tuple of validation status and list of error messages

    Examples:
        >>> validate_config({"api": 8000})
        (True, [])

        >>> validate_config({"invalid name!": 8000})
        (False, ["Invalid route name: 'invalid name!'"])
    """
    errors: list[str] = []

    # Load config if not provided
    if config_data is None:
        if config_file is None:
            config_file = Config().config_file

        # Check file exists
        if not config_file.exists():
            errors.append(f"Config file not found: {config_file}")
            return (False, errors)

        # Check file is readable
        try:
            with open(config_file) as f:
                config_data = json.load(f)
        except PermissionError:
            errors.append(f"Config file not readable: {config_file}")
            return (False, errors)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in config file: {e}")
            return (False, errors)
        except OSError as e:
            errors.append(f"Error reading config file: {e}")
            return (False, errors)

        # Check file permissions (Unix only)
        if hasattr(os, "stat") and os.name != "nt":
            try:
                import stat

                st = config_file.stat()
                # Check if world-writable (security risk)
                if st.st_mode & stat.S_IWOTH:
                    errors.append(f"Config file is world-writable (security risk): {config_file}")
            except OSError:
                pass  # Permission check is optional

    # Validate structure
    if not isinstance(config_data, dict):
        errors.append(f"Config must be a JSON object, got {type(config_data).__name__}")
        return (False, errors)

    # Validate each route
    from .router.security import MAX_ROUTE_NAME_LENGTH
    from .validation import parse_target

    seen_names: set[str] = set()

    for name, target in config_data.items():
        # Validate route name
        if not isinstance(name, str):
            errors.append(f"Route name must be string, got {type(name).__name__}: {name}")
            continue

        # Check for duplicates (case-insensitive)
        name_lower = name.lower()
        if name_lower in seen_names:
            errors.append(f"Duplicate route name (case-insensitive): '{name}'")
        seen_names.add(name_lower)

        # Validate name format
        if not name:
            errors.append("Route name cannot be empty")
            continue

        if not all(c.isalnum() or c == "-" for c in name):
            errors.append(f"Invalid route name '{name}': must contain only letters, numbers, and hyphens")
            continue

        if len(name) > MAX_ROUTE_NAME_LENGTH:
            errors.append(f"Route name '{name}' too long: {len(name)} chars (max {MAX_ROUTE_NAME_LENGTH})")
            continue

        # Validate target value
        if not isinstance(target, (int, str)):
            errors.append(f"Invalid target for '{name}': must be int or string, got {type(target).__name__}")
            continue

        # Parse and validate target
        target_str = str(target)
        parsed = parse_target(target_str)
        if parsed is None:
            errors.append(f"Invalid target for '{name}': {target_str}")
            continue

        scheme, host, port = parsed

        # Validate port range
        if not (1 <= port <= 65535):
            errors.append(f"Invalid port for '{name}': {port} (must be 1-65535)")
            continue

        # Validate scheme
        if scheme not in {"http", "https"}:
            errors.append(f"Invalid scheme for '{name}': {scheme} (only http/https allowed)")
            continue

    # Return validation result
    is_valid = len(errors) == 0
    if is_valid:
        logger.debug("Config validation passed: %d routes", len(config_data))
    else:
        logger.warning("Config validation failed with %d errors", len(errors))

    return (is_valid, errors)
