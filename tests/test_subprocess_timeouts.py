"""
Tests for subprocess timeout enforcement (Phase 4 L-12).
"""

import unittest

from devhost_cli.subprocess_timeouts import (
    TIMEOUT_EXTENDED,
    TIMEOUT_LONG,
    TIMEOUT_NONE,
    TIMEOUT_QUICK,
    TIMEOUT_STANDARD,
    TIMEOUTS,
    get_timeout,
)


class TestSubprocessTimeouts(unittest.TestCase):
    """Test subprocess timeout constants and helpers."""

    def test_timeout_constants(self):
        """Test that timeout constants are reasonable values."""
        self.assertEqual(TIMEOUT_QUICK, 5)
        self.assertEqual(TIMEOUT_STANDARD, 30)
        self.assertEqual(TIMEOUT_LONG, 60)
        self.assertEqual(TIMEOUT_EXTENDED, 120)
        self.assertIsNone(TIMEOUT_NONE)

    def test_timeout_ordering(self):
        """Test that timeouts are in ascending order."""
        self.assertLess(TIMEOUT_QUICK, TIMEOUT_STANDARD)
        self.assertLess(TIMEOUT_STANDARD, TIMEOUT_LONG)
        self.assertLess(TIMEOUT_LONG, TIMEOUT_EXTENDED)

    def test_caddy_timeouts_defined(self):
        """Test that all Caddy operations have defined timeouts."""
        expected_caddy_ops = [
            "caddy_version",
            "caddy_validate",
            "caddy_start",
            "caddy_stop",
            "caddy_reload",
            "caddy_fmt",
        ]
        for op in expected_caddy_ops:
            self.assertIn(op, TIMEOUTS, f"{op} should have a defined timeout")
            timeout = TIMEOUTS[op]
            self.assertIsNotNone(timeout, f"{op} timeout should not be None")
            self.assertIsInstance(timeout, int, f"{op} timeout should be an integer")
            self.assertGreater(timeout, 0, f"{op} timeout should be positive")

    def test_system_timeouts_defined(self):
        """Test that system operations have defined timeouts."""
        expected_system_ops = [
            "systemctl",
            "sudo",
            "powershell",
            "wsl",
            "nssm",
            "taskkill",
        ]
        for op in expected_system_ops:
            self.assertIn(op, TIMEOUTS, f"{op} should have a defined timeout")

    def test_get_timeout_known_operation(self):
        """Test getting timeout for known operations."""
        self.assertEqual(get_timeout("caddy_version"), TIMEOUT_QUICK)
        self.assertEqual(get_timeout("caddy_validate"), TIMEOUT_LONG)
        self.assertEqual(get_timeout("caddy_start"), TIMEOUT_STANDARD)

    def test_get_timeout_unknown_operation(self):
        """Test getting timeout for unknown operation returns default."""
        self.assertEqual(get_timeout("unknown_operation"), TIMEOUT_STANDARD)
        self.assertEqual(get_timeout("unknown_operation", default=60), 60)

    def test_get_timeout_editor_is_none(self):
        """Test that editor operations have no timeout (interactive)."""
        self.assertIsNone(get_timeout("editor"))

    def test_caddy_validate_has_long_timeout(self):
        """Test that caddy validate has a longer timeout (can be slow)."""
        validate_timeout = get_timeout("caddy_validate")
        version_timeout = get_timeout("caddy_version")
        self.assertGreater(validate_timeout, version_timeout)
        self.assertEqual(validate_timeout, TIMEOUT_LONG)

    def test_tunnel_operations_have_extended_timeout(self):
        """Test that tunnel operations have extended timeouts."""
        cloudflared_timeout = get_timeout("cloudflared_start")
        ngrok_timeout = get_timeout("ngrok_start")
        self.assertEqual(cloudflared_timeout, TIMEOUT_EXTENDED)
        self.assertEqual(ngrok_timeout, TIMEOUT_EXTENDED)

    def test_quick_operations(self):
        """Test that quick operations have short timeouts."""
        quick_ops = ["caddy_version", "openssl", "taskkill", "browser_open"]
        for op in quick_ops:
            timeout = get_timeout(op)
            self.assertLessEqual(timeout, TIMEOUT_QUICK, f"{op} should be quick")


if __name__ == "__main__":
    unittest.main()
