"""Tests for router cache module"""

import asyncio
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from devhost_cli.router.cache import RouteCache, _config_candidates, _load_routes_from_path, _select_config_path


class CacheTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        """Set up test environment"""
        self.default_config_path = os.getenv("DEVHOST_CONFIG", "")

    def tearDown(self):
        """Clean up test environment"""
        if self.default_config_path:
            os.environ["DEVHOST_CONFIG"] = self.default_config_path
        elif "DEVHOST_CONFIG" in os.environ:
            del os.environ["DEVHOST_CONFIG"]

    def _write_config(self, data: dict) -> str:
        """Write a temporary config file"""
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        return path

    async def test_route_cache_reload_on_change(self):
        """Test that cache reloads when file changes"""
        path = self._write_config({"hello": 3000})
        os.environ["DEVHOST_CONFIG"] = path

        try:
            cache = RouteCache()

            # First load
            routes1 = await cache.get_routes()
            self.assertEqual(routes1, {"hello": 3000})

            # Modify file
            time.sleep(0.01)  # Ensure mtime changes
            with open(path, "w") as f:
                json.dump({"hello": 3000, "api": 8080}, f)

            # Should reload
            routes2 = await cache.get_routes()
            self.assertEqual(routes2, {"hello": 3000, "api": 8080})

        finally:
            os.unlink(path)

    async def test_route_cache_no_reload_if_unchanged(self):
        """Test that cache doesn't reload if file unchanged"""
        path = self._write_config({"hello": 3000})
        os.environ["DEVHOST_CONFIG"] = path

        try:
            cache = RouteCache()

            # First load
            routes1 = await cache.get_routes()
            self.assertEqual(routes1, {"hello": 3000})

            # Second load (no file change)
            routes2 = await cache.get_routes()
            self.assertIs(routes2, routes1)  # Should be same object

        finally:
            os.unlink(path)

    async def test_route_cache_handles_missing_file(self):
        """Test cache behavior when config file is missing"""
        from unittest.mock import patch
        
        # Mock _select_config_path to return None (no config found)
        with patch('devhost_cli.router.cache._select_config_path', return_value=None):
            cache = RouteCache()
            routes = await cache.get_routes()
            self.assertEqual(routes, {})

    async def test_route_cache_handles_invalid_json(self):
        """Test cache behavior with invalid JSON"""
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            f.write("invalid json {")

        os.environ["DEVHOST_CONFIG"] = path

        try:
            cache = RouteCache()
            routes = await cache.get_routes()
            self.assertEqual(routes, {})  # Should return empty dict on error

        finally:
            os.unlink(path)

    def test_config_candidates_includes_env_var(self):
        """Test that DEVHOST_CONFIG env var is first candidate"""
        os.environ["DEVHOST_CONFIG"] = "/custom/path.json"

        try:
            candidates = _config_candidates()
            self.assertEqual(candidates[0], Path("/custom/path.json"))

        finally:
            del os.environ["DEVHOST_CONFIG"]

    def test_load_routes_from_path_normalizes_keys(self):
        """Test that route names are lowercased"""
        path = self._write_config({"Hello": 3000, "API": 8080})

        try:
            routes = _load_routes_from_path(Path(path))
            self.assertEqual(routes, {"hello": 3000, "api": 8080})

        finally:
            os.unlink(path)

    def test_load_routes_from_path_empty_file(self):
        """Test loading from empty file"""
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)  # Empty file

        try:
            routes = _load_routes_from_path(Path(path))
            self.assertEqual(routes, {})

        finally:
            os.unlink(path)

    def test_select_config_path_returns_first_existing(self):
        """Test that first existing config is selected"""
        path = self._write_config({"test": 1})
        os.environ["DEVHOST_CONFIG"] = path

        try:
            selected = _select_config_path()
            self.assertEqual(selected, Path(path))

        finally:
            os.unlink(path)
            del os.environ["DEVHOST_CONFIG"]


if __name__ == "__main__":
    unittest.main()
