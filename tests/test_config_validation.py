"""
Tests for config validation on startup (Phase 4 L-20).
"""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from devhost_cli.config import validate_config, Config


class TestConfigValidation(unittest.TestCase):
    """Test config validation function."""
    
    def test_empty_config_valid(self):
        """Test that empty config is valid."""
        is_valid, errors = validate_config({})
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
    
    def test_simple_port_config_valid(self):
        """Test that simple port config is valid."""
        config = {
            "api": 8000,
            "web": 3000,
        }
        is_valid, errors = validate_config(config)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
    
    def test_host_port_config_valid(self):
        """Test that host:port config is valid."""
        config = {
            "api": "localhost:8000",
            "db": "127.0.0.1:5432",
        }
        is_valid, errors = validate_config(config)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
    
    def test_url_config_valid(self):
        """Test that URL config is valid."""
        config = {
            "api": "http://localhost:8000",
            "secure": "https://localhost:8443",
        }
        is_valid, errors = validate_config(config)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
    
    def test_invalid_route_name_special_chars(self):
        """Test that route names with special chars are rejected."""
        config = {
            "invalid!name": 8000,
        }
        is_valid, errors = validate_config(config)
        self.assertFalse(is_valid)
        self.assertEqual(len(errors), 1)
        self.assertIn("invalid!name", errors[0])
        self.assertIn("letters, numbers, and hyphens", errors[0])
    
    def test_invalid_route_name_too_long(self):
        """Test that route names exceeding 63 chars are rejected."""
        config = {
            "a" * 64: 8000,  # 64 chars (exceeds RFC 1035 limit)
        }
        is_valid, errors = validate_config(config)
        self.assertFalse(is_valid)
        self.assertEqual(len(errors), 1)
        self.assertIn("too long", errors[0].lower())
        self.assertIn("63", errors[0])
    
    def test_empty_route_name(self):
        """Test that empty route name is rejected."""
        config = {
            "": 8000,
        }
        is_valid, errors = validate_config(config)
        self.assertFalse(is_valid)
        self.assertIn("empty", errors[0].lower())
    
    def test_duplicate_route_names_case_insensitive(self):
        """Test that duplicate route names (case-insensitive) are detected."""
        config = {
            "api": 8000,
            "API": 8001,  # Duplicate (case-insensitive)
        }
        is_valid, errors = validate_config(config)
        self.assertFalse(is_valid)
        self.assertTrue(any("duplicate" in e.lower() for e in errors))
    
    def test_invalid_target_type(self):
        """Test that invalid target types are rejected."""
        config = {
            "api": ["list", "not", "valid"],  # List is not valid
        }
        is_valid, errors = validate_config(config)
        self.assertFalse(is_valid)
        self.assertIn("must be int or string", errors[0])
    
    def test_invalid_port_range_too_low(self):
        """Test that port 0 is rejected."""
        config = {
            "api": 0,  # Port 0 is invalid
        }
        is_valid, errors = validate_config(config)
        self.assertFalse(is_valid)
        self.assertIn("invalid target", errors[0].lower())
    
    def test_invalid_port_range_too_high(self):
        """Test that port > 65535 is rejected."""
        config = {
            "api": 65536,  # Exceeds max port
        }
        is_valid, errors = validate_config(config)
        self.assertFalse(is_valid)
        self.assertIn("invalid target", errors[0].lower())
    
    def test_invalid_scheme_ftp(self):
        """Test that non-http/https schemes are rejected."""
        config = {
            "ftp": "ftp://localhost:21",
        }
        is_valid, errors = validate_config(config)
        self.assertFalse(is_valid)
        # parse_target() rejects this before we check scheme, so error is "Invalid target"
        self.assertIn("invalid target", errors[0].lower())
    
    def test_valid_max_length_route_name(self):
        """Test that 63-char route name is accepted."""
        config = {
            "a" * 63: 8000,  # Exactly 63 chars (RFC 1035 limit)
        }
        is_valid, errors = validate_config(config)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
    
    def test_multiple_errors_collected(self):
        """Test that multiple errors are collected."""
        config = {
            "invalid!name": 8000,
            "a" * 64: 8001,
            "api": 0,
            "ftp": "ftp://localhost:21",
        }
        is_valid, errors = validate_config(config)
        self.assertFalse(is_valid)
        self.assertGreaterEqual(len(errors), 4)  # At least 4 errors
    
    def test_non_dict_config_rejected(self):
        """Test that non-dict config is rejected."""
        is_valid, errors = validate_config([1, 2, 3])  # List instead of dict
        self.assertFalse(is_valid)
        self.assertIn("must be a JSON object", errors[0])


class TestConfigFileValidation(unittest.TestCase):
    """Test config file validation."""
    
    def setUp(self):
        """Create temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_valid_config_file(self):
        """Test validation of valid config file."""
        config_file = self.temp_path / "devhost.json"
        config_file.write_text('{"api": 8000, "web": 3000}')
        
        is_valid, errors = validate_config(config_file=config_file)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
    
    def test_nonexistent_config_file(self):
        """Test that nonexistent config file is detected."""
        config_file = self.temp_path / "nonexistent.json"
        
        is_valid, errors = validate_config(config_file=config_file)
        self.assertFalse(is_valid)
        self.assertIn("not found", errors[0].lower())
    
    def test_invalid_json_file(self):
        """Test that invalid JSON is detected."""
        config_file = self.temp_path / "invalid.json"
        config_file.write_text('{"api": invalid json}')
        
        is_valid, errors = validate_config(config_file=config_file)
        self.assertFalse(is_valid)
        self.assertIn("invalid json", errors[0].lower())
    
    @unittest.skipIf(os.name == "nt", "Unix permissions test")
    def test_world_writable_file_detected(self):
        """Test that world-writable config file is detected."""
        config_file = self.temp_path / "writable.json"
        config_file.write_text('{"api": 8000}')
        
        # Make world-writable
        config_file.chmod(0o666)  # rw-rw-rw-
        
        is_valid, errors = validate_config(config_file=config_file)
        self.assertFalse(is_valid)
        self.assertIn("world-writable", errors[0].lower())
    
    @unittest.skipIf(os.name == "nt", "Unix permissions test")
    def test_secure_permissions_accepted(self):
        """Test that secure permissions are accepted."""
        config_file = self.temp_path / "secure.json"
        config_file.write_text('{"api": 8000}')
        
        # Make read-only for owner
        config_file.chmod(0o600)  # rw-------
        
        is_valid, errors = validate_config(config_file=config_file)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
    
    def test_load_default_config_file(self):
        """Test loading default config file location."""
        # This should load from ~/.devhost/devhost.json
        # We don't check validity, just that it doesn't crash
        is_valid, errors = validate_config()
        # Should be valid (empty or existing config)
        # If invalid, at least shouldn't crash
        self.assertIsInstance(is_valid, bool)
        self.assertIsInstance(errors, list)


class TestConfigIntegration(unittest.TestCase):
    """Test config validation integration."""
    
    def test_validate_after_save(self):
        """Test that saved config can be validated."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create config with custom path
            with patch.dict(os.environ, {"DEVHOST_CONFIG": f"{temp_dir}/devhost.json"}):
                config = Config()
                
                # Save valid config
                config.save({"api": 8000, "web": 3000})
                
                # Validate
                is_valid, errors = validate_config(config_file=config.config_file)
                self.assertTrue(is_valid)
                self.assertEqual(errors, [])
    
    def test_validate_invalid_saved_config(self):
        """Test validation catches errors in saved config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create config with custom path
            with patch.dict(os.environ, {"DEVHOST_CONFIG": f"{temp_dir}/devhost.json"}):
                config = Config()
                
                # Save invalid config
                config.save({"invalid!name": 8000})
                
                # Validate
                is_valid, errors = validate_config(config_file=config.config_file)
                self.assertFalse(is_valid)
                self.assertGreater(len(errors), 0)


class TestConfigValidationEdgeCases(unittest.TestCase):
    """Test edge cases in config validation."""
    
    def test_route_name_with_hyphens(self):
        """Test that route names with hyphens are valid."""
        config = {
            "my-api": 8000,
            "web-server": 3000,
        }
        is_valid, errors = validate_config(config)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
    
    def test_route_name_all_numbers(self):
        """Test that route names with only numbers are valid."""
        config = {
            "123": 8000,
        }
        is_valid, errors = validate_config(config)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
    
    def test_port_as_string(self):
        """Test that port numbers as strings are valid."""
        config = {
            "api": "8000",  # String port
        }
        is_valid, errors = validate_config(config)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
    
    def test_localhost_variants(self):
        """Test various localhost formats."""
        config = {
            "api1": "localhost:8000",
            "api2": "127.0.0.1:8001",
            "api3": "0.0.0.0:8002",
        }
        is_valid, errors = validate_config(config)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
    
    def test_privileged_ports(self):
        """Test that privileged ports are accepted (validation warns but doesn't reject)."""
        config = {
            "http": 80,
            "https": 443,
        }
        # Should be valid (validation doesn't reject privileged ports)
        is_valid, errors = validate_config(config)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
