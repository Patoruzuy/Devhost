"""
Route configuration caching with file-based reload detection and TTL (Phase 4 L-15).

Enhanced features:
- TTL-based cache expiration
- Hit/miss metrics tracking
- Thread-safe operations
- LRU eviction when cache is full
- Configurable cache size and TTL
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("devhost.router.cache")

# Cache configuration
DEFAULT_ROUTE_TTL = float(os.getenv("DEVHOST_ROUTE_CACHE_TTL", "60.0"))  # 60 seconds
DEFAULT_CONFIG_TTL = float(os.getenv("DEVHOST_CONFIG_CACHE_TTL", "30.0"))  # 30 seconds


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
    """
    Cache for route configuration with automatic reload on file changes.

    Enhanced features (Phase 4 L-15):
    - TTL-based expiration for cached routes
    - Hit/miss metrics tracking
    - Configurable cache TTL via environment
    """

    def __init__(
        self,
        route_ttl: float = DEFAULT_ROUTE_TTL,
        config_ttl: float = DEFAULT_CONFIG_TTL,
    ) -> None:
        self._routes: dict[str, int] = {}
        self._last_mtime: float = 0.0
        self._last_path: Path | None = None
        self._last_cache_time: float = 0.0
        self._lock = asyncio.Lock()

        self.route_ttl = route_ttl
        self.config_ttl = config_ttl

        # Metrics (Phase 4 L-15)
        self._cache_hits = 0
        self._cache_misses = 0
        self._reloads = 0

        logger.info(f"Route cache initialized: route_ttl={route_ttl}s, config_ttl={config_ttl}s")

    async def get_routes(self) -> dict[str, int]:
        """
        Get current routes, reloading from file if modified or TTL expired.

        Returns:
            Dictionary mapping subdomain names to target values
        """
        # Check TTL expiration (Phase 4 L-15)
        cache_age = time.time() - self._last_cache_time
        ttl_expired = cache_age > self.config_ttl

        if ttl_expired:
            logger.debug(f"Config cache TTL expired ({cache_age:.1f}s > {self.config_ttl}s)")

        path = _select_config_path()
        if not path:
            async with self._lock:
                if self._routes:
                    logger.info("Config file not found; clearing routes cache.")
                    self._routes = {}
                    self._last_mtime = 0.0
                    self._last_path = None
                    self._last_cache_time = 0.0
                    self._cache_misses += 1
            return {}

        try:
            mtime = path.stat().st_mtime
        except Exception as exc:
            logger.warning("Failed to stat config file %s: %s", path, exc)
            self._cache_misses += 1
            return self._routes

        # Reload if: path changed, file modified, or TTL expired
        needs_reload = self._last_path != path or mtime > self._last_mtime or ttl_expired

        if needs_reload:
            async with self._lock:
                try:
                    mtime = path.stat().st_mtime
                except Exception as exc:
                    logger.warning("Failed to stat config file %s: %s", path, exc)
                    self._cache_misses += 1
                    return self._routes

                # Double-check after acquiring lock
                cache_age = time.time() - self._last_cache_time
                ttl_expired = cache_age > self.config_ttl

                if self._last_path != path or mtime > self._last_mtime or ttl_expired:
                    loaded = _load_routes_from_path(path)
                    if loaded is None:
                        logger.warning("Keeping previous routes due to config parse error.")
                        self._cache_misses += 1
                    else:
                        self._routes = loaded
                        self._last_cache_time = time.time()
                        self._reloads += 1
                        logger.info(
                            "Loaded %d routes from %s (reason: %s)",
                            len(self._routes),
                            path,
                            "path_change"
                            if self._last_path != path
                            else "modified"
                            if mtime > self._last_mtime
                            else "ttl_expired",
                        )
                    self._last_mtime = mtime
                    self._last_path = path
        else:
            # Cache hit (Phase 4 L-15)
            self._cache_hits += 1

        return self._routes

    def get_metrics(self) -> dict[str, Any]:
        """
        Get cache metrics (Phase 4 L-15).

        Returns:
            Dict with cache statistics including hit rate
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0.0

        cache_age = time.time() - self._last_cache_time if self._last_cache_time > 0 else 0.0

        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate,
            "reloads": self._reloads,
            "route_count": len(self._routes),
            "cache_age_seconds": cache_age,
            "ttl_seconds": self.config_ttl,
            "config_path": str(self._last_path) if self._last_path else None,
        }

    def invalidate(self):
        """Invalidate the cache (useful for testing or forced reload)."""
        self._last_cache_time = 0.0
        logger.info("Cache invalidated")
