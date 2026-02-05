"""Session state for the TUI (draft changes before Apply)."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from devhost_cli.state import StateConfig


class SessionState:
    """Draft state that is only persisted on Apply."""

    def __init__(self, state: StateConfig):
        self._state = state
        self._base = deepcopy(state.raw)
        self._draft = deepcopy(state.raw)

    def reset(self) -> None:
        self._base = deepcopy(self._state.raw)
        self._draft = deepcopy(self._state.raw)

    def has_changes(self) -> bool:
        return self._draft != self._base

    @property
    def raw(self) -> dict[str, Any]:
        return self._draft

    @property
    def devhost_dir(self) -> Path:
        return self._state.devhost_dir

    @property
    def routes(self) -> dict[str, dict]:
        return self._draft.get("routes", {})

    def get_route(self, name: str) -> dict | None:
        return self.routes.get(name)

    def set_route(self, name: str, upstream: str, domain: str, enabled: bool = True, tags: list | None = None) -> None:
        self._draft.setdefault("routes", {})[name] = {
            "upstream": upstream,
            "domain": domain,
            "enabled": enabled,
            "tags": tags or [],
        }

    def remove_route(self, name: str) -> None:
        if name in self._draft.get("routes", {}):
            del self._draft["routes"][name]

    @property
    def proxy_mode(self) -> str:
        return self._draft.get("proxy", {}).get("mode", "gateway")

    def set_proxy_mode(self, mode: str) -> None:
        self._draft.setdefault("proxy", {})["mode"] = mode

    @property
    def system_domain(self) -> str:
        return self._draft.get("proxy", {}).get("system", {}).get("domain", "localhost")

    @property
    def external_driver(self) -> str:
        return self._draft.get("proxy", {}).get("external", {}).get("driver", "caddy")

    def set_external_config(self, driver: str, config_path: str | None = None) -> None:
        external = self._draft.setdefault("proxy", {}).setdefault("external", {})
        external["driver"] = driver
        if config_path:
            external["config_path"] = config_path

    @property
    def snippet_path(self) -> Path:
        driver = self.external_driver
        custom = self._draft.get("proxy", {}).get("external", {}).get("snippet_path")
        if custom:
            return Path(custom)
        extensions = {"caddy": "caddy", "nginx": "conf", "traefik": "yml"}
        ext = extensions.get(driver, "conf")
        return self._state.devhost_dir / "proxy" / driver / f"devhost.{ext}"

    @property
    def gateway_listen(self) -> str:
        return self._draft.get("proxy", {}).get("gateway", {}).get("listen", "127.0.0.1:7777")

    @property
    def gateway_port(self) -> int:
        listen = self.gateway_listen
        if ":" in listen:
            return int(listen.split(":")[-1])
        return 7777

    def check_all_integrity(self) -> dict[str, tuple[bool, str]]:
        return self._state.check_all_integrity()
