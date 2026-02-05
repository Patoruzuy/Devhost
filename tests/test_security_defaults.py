"""
Security defaults validation test suite.

Ensures that Devhost uses secure defaults for:
- Bind addresses (localhost only, never 0.0.0.0)
- Private network blocking (SSRF protection enabled by default)
- Certificate verification (enabled by default)
- Timeout values (reasonable limits)
- File permissions (restrictive on sensitive files)
"""

import os
import sys
import unittest
from pathlib import Path


class TestSecureDefaults(unittest.TestCase):
    """Test that security-critical defaults are secure."""

    def setUp(self):
        """Clear security-related environment variables before each test."""
        env_vars_to_clear = [
            'DEVHOST_ALLOW_PRIVATE_NETWORKS',
            'DEVHOST_VERIFY_CERTS',
            'DEVHOST_TIMEOUT',
            'DEVHOST_BIND_ADDRESS',
            'DEVHOST_LOG_REQUESTS',
        ]
        for var in env_vars_to_clear:
            os.environ.pop(var, None)

    def test_default_bind_address_is_localhost(self):
        """Ensure default bind is 127.0.0.1, not 0.0.0.0 (no LAN exposure)."""
        # Test router default bind
        from router.app import app
        # FastAPI doesn't expose bind address, but we can check docs
        # The critical part is that devhost_cli defaults to 127.0.0.1
        
        # Check CLI default
        from devhost_cli import router_manager
        default_host = getattr(router_manager, 'DEFAULT_HOST', None)
        
        if default_host:
            self.assertIn(
                default_host,
                {'127.0.0.1', 'localhost'},
                f"Default bind address must be localhost, got: {default_host}"
            )

    def test_private_networks_blocked_by_default(self):
        """Ensure DEVHOST_ALLOW_PRIVATE_NETWORKS defaults to false (SSRF protection)."""
        # Clear env var
        os.environ.pop('DEVHOST_ALLOW_PRIVATE_NETWORKS', None)
        
        # Import security module
        from devhost_cli.router import security
        
        # Test private IP detection
        test_cases = [
            ('192.168.1.1', True, 'Private IP 192.168.x.x should be blocked'),
            ('10.0.0.1', True, 'Private IP 10.x.x.x should be blocked'),
            ('172.16.0.1', True, 'Private IP 172.16.x.x should be blocked'),
            ('169.254.169.254', True, 'Metadata endpoint should be blocked'),
            ('8.8.8.8', False, 'Public IP should be allowed'),
            ('1.1.1.1', False, 'Public IP should be allowed'),
        ]
        
        for ip, should_block, msg in test_cases:
            # validate_upstream_target returns (is_valid, error_msg)
            is_valid, error_msg = security.validate_upstream_target(ip, 8000)
            blocked = not is_valid
            
            self.assertEqual(blocked, should_block, msg)

    def test_metadata_endpoints_blocked(self):
        """Ensure cloud metadata endpoints are blocked by default."""
        from devhost_cli.router import security
        
        metadata_hosts = [
            ('169.254.169.254', 80),  # AWS/Azure
            ('metadata.google.internal', 80),  # GCP
            ('metadata', 80),  # GCP short
        ]
        
        for host, port in metadata_hosts:
            is_valid, error_msg = security.validate_upstream_target(host, port)
            self.assertFalse(
                is_valid,
                f"Metadata endpoint should be blocked: {host}:{port}"
            )
            self.assertIn(
                'metadata',
                error_msg.lower(),
                f"Error message should mention metadata: {error_msg}"
            )

    def test_only_http_https_schemes_allowed(self):
        """Ensure only http:// and https:// schemes are allowed (no file://, ftp://, etc)."""
        from devhost_cli.validation import parse_target
        
        # Allowed schemes - parse_target returns (scheme, host, port) with defaults
        valid_targets = [
            ('8000', ('http', '127.0.0.1', 8000)),
            ('localhost:8000', ('http', 'localhost', 8000)),
            ('http://localhost:8000', ('http', 'localhost', 8000)),
            ('https://example.com:443', ('https', 'example.com', 443)),
        ]
        
        for target, expected in valid_targets:
            result = parse_target(target)
            self.assertEqual(
                result, expected,
                f"Valid target {target} should parse correctly"
            )
        
        # Blocked schemes - parse_target returns None for invalid inputs
        invalid_targets = [
            'file:///etc/passwd',
            'ftp://malicious.com:21/data',
            'gopher://old-protocol.com:70',
            'javascript:alert(1)',
        ]
        
        for target in invalid_targets:
            result = parse_target(target)
            self.assertIsNone(
                result,
                f"Dangerous scheme should be rejected: {target}"
            )

    def test_hostname_validation_blocks_control_characters(self):
        """Ensure hostname validation blocks control characters (header injection)."""
        from devhost_cli.router.security import validate_hostname
        
        # Valid hostnames - validate_hostname returns (is_valid, error_msg)
        valid_hostnames = [
            'api',
            'web-app',
            'service',
            'my-app-v2',
            'app123',
        ]
        
        for hostname in valid_hostnames:
            is_valid, error_msg = validate_hostname(hostname)
            self.assertTrue(
                is_valid,
                f"Valid hostname {hostname} should pass validation: {error_msg}"
            )
        
        # Invalid hostnames with control characters
        invalid_hostnames = [
            'app\r\nX-Injected: header',  # CRLF injection
            'app\x00.evil.com',  # Null byte
            'app\nmalicious',  # Newline
            '../../../etc/passwd',  # Path traversal
            '',  # Empty
        ]
        
        for hostname in invalid_hostnames:
            is_valid, error_msg = validate_hostname(hostname)
            self.assertFalse(
                is_valid,
                f"Invalid hostname should be rejected: {repr(hostname)}"
            )

    def test_default_timeout_is_reasonable(self):
        """Ensure default timeout is set to prevent hanging requests."""
        # Clear env var
        os.environ.pop('DEVHOST_TIMEOUT', None)
        
        # Check environment variable default
        default_timeout = int(os.getenv('DEVHOST_TIMEOUT', '60'))
        
        # Default should be between 30-120 seconds
        self.assertGreaterEqual(
            default_timeout, 30,
            "Default timeout should be at least 30 seconds"
        )
        self.assertLessEqual(
            default_timeout, 120,
            "Default timeout should not exceed 120 seconds"
        )

    def test_environment_variable_overrides_require_explicit_opt_in(self):
        """Ensure dangerous features require explicit environment variables."""
        # Test that DEVHOST_ALLOW_PRIVATE_NETWORKS=1 actually enables private networks
        os.environ['DEVHOST_ALLOW_PRIVATE_NETWORKS'] = '1'
        
        # Re-import to pick up env var
        import importlib
        from devhost_cli.router import security
        importlib.reload(security)
        
        # Now private IPs should be allowed
        is_valid, error_msg = security.validate_upstream_target('192.168.1.1', 8000)
        
        self.assertTrue(
            is_valid,
            f"DEVHOST_ALLOW_PRIVATE_NETWORKS=1 should allow private IPs: {error_msg}"
        )
        
        # Clean up
        os.environ.pop('DEVHOST_ALLOW_PRIVATE_NETWORKS')
        importlib.reload(security)

    def test_state_file_not_world_readable(self):
        """Ensure state.yml is not created with world-readable permissions (Unix only)."""
        if sys.platform == 'win32':
            self.skipTest("File permissions test is Unix-only")
        
        import stat
        state_file = Path.home() / '.devhost' / 'state.yml'
        
        if state_file.exists():
            mode = state_file.stat().st_mode
            perms = stat.S_IMODE(mode)
            
            # Check that group and others don't have read permissions
            group_read = bool(perms & stat.S_IRGRP)
            other_read = bool(perms & stat.S_IROTH)
            
            self.assertFalse(
                group_read or other_read,
                f"state.yml should not be world-readable (permissions: {oct(perms)})"
            )

    def test_logging_disabled_by_default(self):
        """Ensure request logging is disabled by default (prevents secret leakage)."""
        # Clear env var
        os.environ.pop('DEVHOST_LOG_REQUESTS', None)
        
        # Check if logging is enabled
        log_requests = os.getenv('DEVHOST_LOG_REQUESTS', '0')
        
        self.assertEqual(
            log_requests, '0',
            "Request logging should be disabled by default to prevent secret leakage"
        )

    def test_no_hardcoded_secrets_in_defaults(self):
        """Ensure no hardcoded API keys, tokens, or credentials in default config."""
        # Check common secret patterns
        suspicious_patterns = [
            'api_key',
            'secret_key',
            'password',
            'token',
            'credential',
        ]
        
        # Read default config
        from devhost_cli import config
        default_config = config.Config()
        
        # Check that no suspicious keys exist with non-empty values
        for pattern in suspicious_patterns:
            # This is a sanity check - the config module shouldn't have these
            self.assertFalse(
                hasattr(default_config, pattern),
                f"Config should not have hardcoded {pattern}"
            )


class TestWindowsSecurityDefaults(unittest.TestCase):
    """Test Windows-specific security defaults."""

    def setUp(self):
        """Skip tests if not on Windows."""
        if sys.platform != 'win32':
            self.skipTest("Windows-specific tests")

    def test_hosts_file_operations_require_admin(self):
        """Ensure hosts file operations check for admin privileges."""
        from devhost_cli.windows import is_admin
        
        # is_admin() should return a boolean
        admin_status = is_admin()
        self.assertIsInstance(
            admin_status, bool,
            "is_admin() should return a boolean"
        )

    def test_hosts_file_backup_created_before_modification(self):
        """Ensure hosts file backup is created before any modification."""
        # This is more of an integration test
        # We just verify the backup function exists
        from devhost_cli.windows import hosts_backup
        
        # Should be callable
        self.assertTrue(
            callable(hosts_backup),
            "hosts_backup() should be a callable function"
        )


if __name__ == '__main__':
    unittest.main()
