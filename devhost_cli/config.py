"""Configuration management for devhost.json and domain settings"""

import json
import os
from pathlib import Path

from .utils import msg_error, msg_success, msg_warning


class Config:
    """Manages devhost.json configuration"""

    def __init__(self):
        # Check environment variable first
        env_path = os.getenv("DEVHOST_CONFIG")
        if env_path:
            self.config_file = Path(env_path).resolve()
            self.script_dir = self.config_file.parent
        else:
            # Use parent directory of this module
            self.script_dir = Path(__file__).parent.parent.resolve()
            self.config_file = self.script_dir / "devhost.json"

        self.domain_file = self.script_dir / ".devhost" / "domain"

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

        # Check domain file
        if self.domain_file.exists():
            try:
                domain = self.domain_file.read_text().strip()
                if domain:
                    return domain
            except OSError:
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
