"""Tests for certificate management and validation

Tests L-05, L-06, L-07 from Phase 3:
- L-05: Certificate storage hardening (permissions)
- L-06: Certificate verification environment variable
- L-07: Certificate expiration warnings
"""

import os
import stat
import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from devhost_cli import certificates


class TestCertificatePermissions(unittest.TestCase):
    """Test certificate private key permission checks (L-05)"""
    
    def setUp(self):
        """Create temporary key file for testing"""
        self.temp_dir = tempfile.mkdtemp()
        self.key_path = Path(self.temp_dir) / "test_private.key"
        self.key_path.write_text("-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n")
    
    def tearDown(self):
        """Clean up temporary files"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @unittest.skipIf(os.name == 'nt', "Unix permissions test")
    def test_insecure_key_permissions_detected(self):
        """Detect world-readable private key (security risk)"""
        # Set insecure permissions (0644 - world-readable)
        self.key_path.chmod(0o644)
        
        is_secure, error_msg = certificates.check_key_permissions(self.key_path)
        
        self.assertFalse(is_secure)
        self.assertIn("world-readable", error_msg.lower())
    
    @unittest.skipIf(os.name == 'nt', "Unix permissions test")
    def test_secure_key_permissions_accepted(self):
        """Accept secure private key permissions (0600)"""
        # Set secure permissions (0600 - owner only)
        self.key_path.chmod(0o600)
        
        is_secure, error_msg = certificates.check_key_permissions(self.key_path)
        
        self.assertTrue(is_secure)
        self.assertEqual(error_msg, "")
    
    @unittest.skipIf(os.name == 'nt', "Unix permissions test")
    def test_set_secure_permissions(self):
        """Set secure permissions on private key file"""
        # Start with insecure permissions
        self.key_path.chmod(0o644)
        
        success, error_msg = certificates.set_secure_key_permissions(self.key_path)
        
        self.assertTrue(success)
        self.assertEqual(error_msg, "")
        
        # Verify permissions changed to 0600
        file_stat = self.key_path.stat()
        mode = stat.S_IMODE(file_stat.st_mode)
        self.assertEqual(mode, 0o600)
    
    @unittest.skipIf(os.name != 'nt', "Windows-only test")
    def test_windows_skips_unix_permissions(self):
        """Windows should skip Unix permission checks"""
        is_secure, error_msg = certificates.check_key_permissions(self.key_path)
        
        # Should return True on Windows (uses NTFS ACLs instead)
        self.assertTrue(is_secure)
        self.assertEqual(error_msg, "")
    
    def test_nonexistent_key_file(self):
        """Handle non-existent key file gracefully"""
        fake_path = Path(self.temp_dir) / "nonexistent.key"
        
        is_secure, error_msg = certificates.check_key_permissions(fake_path)
        
        self.assertFalse(is_secure)
        self.assertIn("does not exist", error_msg)


class TestCertificateExpiration(unittest.TestCase):
    """Test certificate expiration warnings (L-07)"""
    
    def setUp(self):
        """Create temporary cert file for testing"""
        self.temp_dir = tempfile.mkdtemp()
        self.cert_path = Path(self.temp_dir) / "test_cert.pem"
    
    def tearDown(self):
        """Clean up temporary files"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_nonexistent_certificate_file(self):
        """Handle non-existent certificate file gracefully"""
        fake_path = Path(self.temp_dir) / "nonexistent.pem"
        
        is_expiring, exp_date, message = certificates.check_certificate_expiration(fake_path)
        
        self.assertFalse(is_expiring)
        self.assertIsNone(exp_date)
        self.assertIn("does not exist", message)
    
    def test_certificate_check_returns_proper_structure(self):
        """Certificate expiration check returns tuple with proper structure"""
        # Create a fake certificate file
        self.cert_path.write_bytes(b"fake cert data")
        
        result = certificates.check_certificate_expiration(self.cert_path)
        
        # Should return tuple of (bool, datetime or None, str)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], bool)  # is_expiring
        # result[1] can be datetime or None
        self.assertIsInstance(result[2], str)  # message


class TestCertificateVerification(unittest.TestCase):
    """Test certificate verification configuration (L-06)"""
    
    def test_verify_certs_default_enabled(self):
        """Certificate verification should be enabled by default"""
        # Clear environment variable
        os.environ.pop('DEVHOST_VERIFY_CERTS', None)
        
        should_verify = certificates.should_verify_certificates()
        
        self.assertTrue(should_verify)
    
    def test_verify_certs_explicit_disable(self):
        """Allow disabling certificate verification via environment variable"""
        os.environ['DEVHOST_VERIFY_CERTS'] = '0'
        
        should_verify = certificates.should_verify_certificates()
        
        self.assertFalse(should_verify)
        
        # Cleanup
        os.environ.pop('DEVHOST_VERIFY_CERTS', None)
    
    def test_verify_certs_various_true_values(self):
        """Accept various true values for DEVHOST_VERIFY_CERTS"""
        for value in ['1', 'true', 'True', 'TRUE', 'yes', 'Yes', 'YES', 'on', 'On', 'ON']:
            os.environ['DEVHOST_VERIFY_CERTS'] = value
            
            should_verify = certificates.should_verify_certificates()
            
            self.assertTrue(should_verify, f"Failed for value: {value}")
        
        # Cleanup
        os.environ.pop('DEVHOST_VERIFY_CERTS', None)
    
    def test_verify_certs_various_false_values(self):
        """Accept various false values for DEVHOST_VERIFY_CERTS"""
        for value in ['0', 'false', 'False', 'FALSE', 'no', 'No', 'NO', 'off', 'Off', 'OFF']:
            os.environ['DEVHOST_VERIFY_CERTS'] = value
            
            should_verify = certificates.should_verify_certificates()
            
            self.assertFalse(should_verify, f"Failed for value: {value}")
        
        # Cleanup
        os.environ.pop('DEVHOST_VERIFY_CERTS', None)


class TestCertificateStorageLocations(unittest.TestCase):
    """Test certificate storage location discovery"""
    
    def test_get_cert_storage_locations(self):
        """Get certificate storage locations"""
        locations = certificates.get_cert_storage_locations()
        
        # Should return a dictionary
        self.assertIsInstance(locations, dict)
        
        # All values should be Path objects
        for name, path in locations.items():
            self.assertIsInstance(path, Path)
            self.assertTrue(path.exists(), f"Location {name} does not exist: {path}")


class TestCertificateValidation(unittest.TestCase):
    """Test comprehensive certificate validation"""
    
    def test_validate_all_certificates_structure(self):
        """Validate certificate validation returns proper structure"""
        results = certificates.validate_all_certificates()
        
        # Check structure
        self.assertIsInstance(results, dict)
        self.assertIn('warnings', results)
        self.assertIn('errors', results)
        self.assertIn('info', results)
        
        # All should be lists
        self.assertIsInstance(results['warnings'], list)
        self.assertIsInstance(results['errors'], list)
        self.assertIsInstance(results['info'], list)
    
    def test_log_certificate_status_no_crash(self):
        """Ensure certificate logging doesn't crash on startup"""
        # Should not raise any exceptions
        try:
            certificates.log_certificate_status()
        except Exception as e:
            self.fail(f"log_certificate_status() raised unexpected exception: {e}")


if __name__ == '__main__':
    unittest.main()
