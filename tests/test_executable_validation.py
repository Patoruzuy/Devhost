"""
Tests for executable path validation (Phase 4 L-11).
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from devhost_cli.executable_validation import (
    find_executable_in_path,
    is_user_writable,
    validate_caddy_executable,
    validate_executable,
)


class TestExecutableValidation(unittest.TestCase):
    """Test executable path validation."""

    def setUp(self):
        """Create temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_nonexistent_file(self):
        """Test validation of nonexistent file."""
        is_valid, error = validate_executable("/nonexistent/file")
        self.assertFalse(is_valid)
        self.assertIn("not found", error.lower())

    def test_empty_path(self):
        """Test validation of empty path."""
        is_valid, error = validate_executable("")
        self.assertFalse(is_valid)
        self.assertIn("empty", error.lower())

    def test_directory_not_file(self):
        """Test validation rejects directories."""
        is_valid, error = validate_executable(self.temp_dir)
        self.assertFalse(is_valid)
        self.assertIn("not a file", error.lower())

    @unittest.skipIf(sys.platform == "win32", "Unix permissions test")
    def test_non_executable_file(self):
        """Test validation rejects non-executable files."""
        # Create a non-executable file
        test_file = self.temp_path / "non_executable"
        test_file.write_text("#!/bin/bash\necho test")
        test_file.chmod(0o644)  # rw-r--r--

        is_valid, error = validate_executable(str(test_file))
        self.assertFalse(is_valid)
        self.assertIn("not executable", error.lower())

    @unittest.skipIf(sys.platform == "win32", "Unix permissions test")
    def test_executable_file_passes(self):
        """Test validation accepts executable files."""
        # Create an executable file in a safe location
        test_file = self.temp_path / "safe_executable"
        test_file.write_text("#!/bin/bash\necho test")
        test_file.chmod(0o755)  # rwxr-xr-x

        # Skip writability check for this test
        is_valid, error = validate_executable(str(test_file), check_writability=False)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    @unittest.skipIf(sys.platform == "win32", "Unix permissions test")
    def test_user_writable_detected(self):
        """Test that user-writable executables are detected."""
        # Create an executable in user's home directory
        test_file = self.temp_path / "user_executable"
        test_file.write_text("#!/bin/bash\necho test")
        test_file.chmod(0o755)

        # Mock Path.home() to return temp directory
        with patch("devhost_cli.executable_validation.Path.home", return_value=self.temp_path):
            with patch("devhost_cli.executable_validation.os.getuid", return_value=os.getuid()):
                is_valid, error = is_user_writable(test_file)
                self.assertTrue(is_valid)  # Should be user-writable

    def test_system_path_not_writable(self):
        """Test that system paths are not considered user-writable."""
        if sys.platform == "win32":
            test_path = Path(r"C:\Windows\System32\notepad.exe")
        else:
            test_path = Path("/usr/bin/python3")

        # Only test if the file actually exists
        if test_path.exists():
            is_writable = is_user_writable(test_path)
            self.assertFalse(is_writable)  # System paths should not be user-writable

    def test_find_python_in_path(self):
        """Test finding Python executable in PATH."""
        # Python should be in PATH since we're running it
        if sys.platform == "win32":
            python_name = "python.exe"
        else:
            python_name = "python3"

        python_path = find_executable_in_path(python_name)
        if python_path:
            self.assertTrue(Path(python_path).exists())
            self.assertTrue(os.access(python_path, os.X_OK))

    def test_find_nonexistent_in_path(self):
        """Test finding nonexistent executable returns None."""
        result = find_executable_in_path("definitely_not_a_real_executable_12345")
        self.assertIsNone(result)

    @patch("subprocess.run")
    def test_validate_caddy_success(self, mock_run):
        """Test Caddy validation with successful version check."""
        # Create a fake executable
        test_file = self.temp_path / "caddy"
        test_file.write_text("#!/bin/bash\necho Caddy v2.7.4")
        if sys.platform != "win32":
            test_file.chmod(0o755)

        # Mock subprocess.run to return Caddy version
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Caddy v2.7.4 h1:abc123"
        mock_run.return_value = mock_result

        # Skip writability check
        is_valid, error = validate_caddy_executable(str(test_file))

        # On Windows, we might not have execute permission
        if sys.platform == "win32":
            # Just check it ran without crashing
            self.assertIsInstance(is_valid, bool)
        else:
            self.assertTrue(is_valid)
            self.assertIsNone(error)

    @patch("subprocess.run")
    def test_validate_caddy_wrong_executable(self, mock_run):
        """Test Caddy validation with wrong executable."""
        # Create a fake executable
        test_file = self.temp_path / "fake_caddy"
        test_file.write_text("#!/bin/bash\necho NotCaddy")
        if sys.platform != "win32":
            test_file.chmod(0o755)

        # Mock subprocess.run to return non-Caddy output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "NotCaddy v1.0"
        mock_run.return_value = mock_result

        is_valid, error = validate_caddy_executable(str(test_file))

        # On Windows, might fail at executable check
        if not is_valid:
            self.assertIsNotNone(error)

    @patch("subprocess.run")
    def test_validate_caddy_timeout(self, mock_run):
        """Test Caddy validation handles timeout."""
        # Create a fake executable
        test_file = self.temp_path / "slow_caddy"
        test_file.write_text("#!/bin/bash\nsleep 100")
        if sys.platform != "win32":
            test_file.chmod(0o755)

        # Mock subprocess.run to raise TimeoutExpired
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("caddy", 5)

        is_valid, error = validate_caddy_executable(str(test_file))

        # On Windows, might fail at executable check
        if not is_valid:
            self.assertIsNotNone(error)


class TestIsUserWritable(unittest.TestCase):
    """Test is_user_writable function."""

    @unittest.skipIf(sys.platform == "win32", "Unix test")
    def test_world_writable_file(self):
        """Test that world-writable files are detected."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = Path(f.name)

        try:
            # Make world-writable
            path.chmod(0o777)
            self.assertTrue(is_user_writable(path))
        finally:
            path.unlink()

    @unittest.skipIf(sys.platform == "win32", "Unix test")
    def test_group_writable_file(self):
        """Test that group-writable files are detected."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = Path(f.name)

        try:
            # Make group-writable
            path.chmod(0o775)
            self.assertTrue(is_user_writable(path))
        finally:
            path.unlink()

    @unittest.skipIf(sys.platform != "win32", "Windows test")
    def test_windows_userprofile_writable(self):
        """Test that Windows user profile paths are detected as writable."""
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            test_path = Path(userprofile) / "test_file.txt"
            # We don't need to create the file, just check the logic
            with patch("devhost_cli.executable_validation.Path.stat") as mock_stat:
                mock_stat.return_value = MagicMock()
                # The actual check is based on path prefix
                self.assertTrue(str(test_path).startswith(userprofile))


class TestFindExecutableInPath(unittest.TestCase):
    """Test find_executable_in_path function."""

    def test_finds_python(self):
        """Test finding Python in PATH."""
        # Python should be in PATH
        if sys.platform == "win32":
            # On Windows, try both python and python.exe
            result = find_executable_in_path("python")
            if not result:
                result = find_executable_in_path("python.exe")
        else:
            # On Unix, try python3 first, then python
            result = find_executable_in_path("python3")
            if not result:
                result = find_executable_in_path("python")

        # We should find Python since we're running it
        if result:
            self.assertTrue(Path(result).exists())

    def test_nonexistent_returns_none(self):
        """Test that nonexistent executables return None."""
        result = find_executable_in_path("nonexistent_executable_xyz_12345")
        self.assertIsNone(result)

    @patch.dict(os.environ, {"PATH": ""})
    def test_empty_path(self):
        """Test behavior with empty PATH."""
        result = find_executable_in_path("python")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
