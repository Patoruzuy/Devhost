"""Configuration management for devhost.json, devhost.yml and domain settings"""

import json
import os
from pathlib import Path

from .utils import msg_error, msg_success, msg_warning

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
