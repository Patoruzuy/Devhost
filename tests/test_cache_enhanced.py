"""
Tests for route cache enhancements (Phase 4 L-15).
"""

import asyncio
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from devhost_cli.router.cache import RouteCache, DEFAULT_ROUTE_TTL, DEFAULT_CONFIG_TTL


class TestRouteCacheEnhanced(unittest.IsolatedAsyncioTestCase):
    """Test enhanced route cache with TTL and metrics."""
    
    def setUp(self):
        """Create temporary config file and cache instance."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "devhost.json"
        
        # Write initial config
        self.initial_routes = {"api": 8000, "web": 3000}
        self.config_path.write_text(json.dumps(self.initial_routes))
        
        # Set environment to use our temp config
        os.environ["DEVHOST_CONFIG"] = str(self.config_path)
        
        # Create cache with short TTL for testing
        self.cache = RouteCache(route_ttl=1.0, config_ttl=1.0)
    
    def tearDown(self):
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if "DEVHOST_CONFIG" in os.environ:
            del os.environ["DEVHOST_CONFIG"]
    
    async def test_initial_load(self):
        """Test initial route loading."""
        routes = await self.cache.get_routes()
        
        self.assertEqual(len(routes), 2)
        self.assertEqual(routes["api"], 8000)
        self.assertEqual(routes["web"], 3000)
    
    async def test_cache_hit(self):
        """Test cache hit on subsequent reads."""
        # First load
        routes1 = await self.cache.get_routes()
        
        # Second load (should be cache hit)
        routes2 = await self.cache.get_routes()
        
        self.assertEqual(routes1, routes2)
        
        # Check metrics
        metrics = self.cache.get_metrics()
        self.assertGreater(metrics["cache_hits"], 0)
    
    async def test_file_modification_detection(self):
        """Test that file modifications trigger reload."""
        # Initial load
        routes1 = await self.cache.get_routes()
        
        # Modify config file
        await asyncio.sleep(0.1)  # Ensure different mtime
        updated_routes = {"api": 8000, "web": 3000, "db": 5432}
        self.config_path.write_text(json.dumps(updated_routes))
        
        # Load again
        routes2 = await self.cache.get_routes()
        
        self.assertEqual(len(routes2), 3)
        self.assertEqual(routes2["db"], 5432)
        
        # Check metrics
        metrics = self.cache.get_metrics()
        self.assertEqual(metrics["reloads"], 2)  # Initial + modification
    
    async def test_ttl_expiration(self):
        """Test that TTL expiration triggers reload."""
        # Initial load
        routes1 = await self.cache.get_routes()
        
        # Wait for TTL to expire
        await asyncio.sleep(1.2)
        
        # Load again (should reload due to TTL)
        routes2 = await self.cache.get_routes()
        
        # Check metrics
        metrics = self.cache.get_metrics()
        self.assertEqual(metrics["reloads"], 2)  # Initial + TTL expiration
        self.assertGreater(metrics["cache_age_seconds"], 0.0)
    
    async def test_cache_invalidation(self):
        """Test manual cache invalidation."""
        # Initial load
        routes1 = await self.cache.get_routes()
        
        # Cache hit
        routes2 = await self.cache.get_routes()
        metrics = self.cache.get_metrics()
        hits_before = metrics["cache_hits"]
        
        # Invalidate
        self.cache.invalidate()
        
        # Next load should reload
        routes3 = await self.cache.get_routes()
        
        metrics = self.cache.get_metrics()
        self.assertEqual(metrics["reloads"], 2)  # Initial + post-invalidation
    
    async def test_metrics_structure(self):
        """Test that metrics contain all expected fields."""
        # Load routes
        await self.cache.get_routes()
        await self.cache.get_routes()  # Cache hit
        
        metrics = self.cache.get_metrics()
        
        # Check all expected fields
        self.assertIn("cache_hits", metrics)
        self.assertIn("cache_misses", metrics)
        self.assertIn("hit_rate", metrics)
        self.assertIn("reloads", metrics)
        self.assertIn("route_count", metrics)
        self.assertIn("cache_age_seconds", metrics)
        self.assertIn("ttl_seconds", metrics)
        self.assertIn("config_path", metrics)
        
        # Check values
        self.assertGreaterEqual(metrics["cache_hits"], 1)
        self.assertGreaterEqual(metrics["hit_rate"], 0.0)
        self.assertLessEqual(metrics["hit_rate"], 1.0)
        self.assertEqual(metrics["route_count"], 2)
        self.assertEqual(metrics["ttl_seconds"], 1.0)
    
    async def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        # Initial load (miss)
        await self.cache.get_routes()
        
        # Multiple cache hits
        await self.cache.get_routes()
        await self.cache.get_routes()
        await self.cache.get_routes()
        
        metrics = self.cache.get_metrics()
        
        # Should have 1 miss and 3 hits = 75% hit rate
        total = metrics["cache_hits"] + metrics["cache_misses"]
        expected_rate = metrics["cache_hits"] / total
        self.assertAlmostEqual(metrics["hit_rate"], expected_rate, places=2)
    
    async def test_config_path_in_metrics(self):
        """Test that config path is reported in metrics."""
        await self.cache.get_routes()
        
        metrics = self.cache.get_metrics()
        
        self.assertIsNotNone(metrics["config_path"])
        self.assertIn("devhost.json", metrics["config_path"])
    
    async def test_empty_config(self):
        """Test handling of empty config file."""
        # Write empty config
        self.config_path.write_text("")
        
        routes = await self.cache.get_routes()
        
        self.assertEqual(len(routes), 0)
        
        metrics = self.cache.get_metrics()
        self.assertEqual(metrics["route_count"], 0)
    
    async def test_invalid_json(self):
        """Test handling of invalid JSON."""
        # Initial load with valid config
        routes1 = await self.cache.get_routes()
        self.assertEqual(len(routes1), 2)
        
        # Write invalid JSON
        await asyncio.sleep(0.1)
        self.config_path.write_text("{invalid json")
        
        # Should keep previous routes
        routes2 = await self.cache.get_routes()
        self.assertEqual(len(routes2), 2)  # Previous routes retained


class TestCacheTTLConfiguration(unittest.TestCase):
    """Test cache TTL configuration via environment variables."""
    
    def test_default_ttl_values(self):
        """Test that default TTL values are correct."""
        self.assertEqual(DEFAULT_ROUTE_TTL, 60.0)
        self.assertEqual(DEFAULT_CONFIG_TTL, 30.0)
    
    def test_custom_ttl_via_constructor(self):
        """Test setting custom TTL via constructor."""
        cache = RouteCache(route_ttl=120.0, config_ttl=60.0)
        
        self.assertEqual(cache.route_ttl, 120.0)
        self.assertEqual(cache.config_ttl, 60.0)
        
        metrics = cache.get_metrics()
        self.assertEqual(metrics["ttl_seconds"], 60.0)


if __name__ == "__main__":
    unittest.main()
