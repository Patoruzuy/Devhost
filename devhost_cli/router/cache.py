"""
Route configuration caching with file-based reload detection.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("devhost.router.cache")


def _config_candidates() -> list[Path]:
    """Return list of candidate config file paths in priority order."""
    candidates = []
    env_path = os.getenv("DEVHOST_CONFIG")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path.home() / ".devhost" / "devhost.json")
    candidates.append(Path.cwd() / "devhost.json")
    here = Path(__file__).resolve()
    # repo root (../../../devhost.json) and legacy router-local file
    candidates.append(here.parent.parent.parent / "devhost.json")
    candidates.append(here.parent.parent / "devhost.json")

    # de-duplicate while preserving order
    seen = set()
    unique = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def _load_routes_from_path(path: Path) -> dict[str, int] | None:
    """Load routes from a JSON config file."""
    try:
        content = path.read_text()
        if not content.strip():
            return {}
        data = json.loads(content)
        if isinstance(data, dict):
            return {str(k).lower(): v for k, v in data.items()}
    except Exception as exc:
        logger.warning("Failed to load config from %s: %s", path, exc)
        return None
    return {}


def _select_config_path() -> Path | None:
    """Select the first existing config file from candidates."""
    for path in _config_candidates():
        try:
            if path.is_file():
                return path
        except Exception:
            continue
    return None


class RouteCache:
    """Cache for route configuration with automatic reload on file changes."""

    def __init__(self) -> None:
        self._routes: dict[str, int] = {}
        self._last_mtime: float = 0.0
        self._last_path: Path | None = None
        self._lock = asyncio.Lock()

    async def get_routes(self) -> dict[str, int]:
        """
        Get current routes, reloading from file if modified.

        Returns:
            Dictionary mapping subdomain names to target values
        """
        path = _select_config_path()
        if not path:
            async with self._lock:
                if self._routes:
                    logger.info("Config file not found; clearing routes cache.")
                    self._routes = {}
                    self._last_mtime = 0.0
                    self._last_path = None
            return {}
        try:
            mtime = path.stat().st_mtime
        except Exception as exc:
            logger.warning("Failed to stat config file %s: %s", path, exc)
            return self._routes

        if self._last_path != path or mtime > self._last_mtime:
            async with self._lock:
                try:
                    mtime = path.stat().st_mtime
                except Exception as exc:
                    logger.warning("Failed to stat config file %s: %s", path, exc)
                    return self._routes
                if self._last_path != path or mtime > self._last_mtime:
                    loaded = _load_routes_from_path(path)
                    if loaded is None:
                        logger.warning("Keeping previous routes due to config parse error.")
                    else:
                        self._routes = loaded
                        logger.info("Loaded %d routes from %s", len(self._routes), path)
                    self._last_mtime = mtime
                    self._last_path = path
        return self._routes
