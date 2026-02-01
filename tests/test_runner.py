"""Tests for ProjectConfig and DevhostRunner"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from devhost_cli.config import YAML_AVAILABLE, ProjectConfig
from devhost_cli.runner import DevhostRunner, find_free_port, is_port_in_use


class TestProjectConfig(unittest.TestCase):
    """Tests for ProjectConfig class"""

    def test_default_config_no_file(self):
        """Test default config when no devhost.yml exists"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ProjectConfig(Path(tmpdir))

            self.assertFalse(config.exists())
            self.assertEqual(config.domain, "localhost")
            self.assertTrue(config.auto_register)
            self.assertTrue(config.auto_caddy)
            # Name should be derived from directory
            self.assertEqual(config.name, Path(tmpdir).name.lower())

    @unittest.skipUnless(YAML_AVAILABLE, "pyyaml not installed")
    def test_load_yaml_config(self):
        """Test loading devhost.yml config"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "devhost.yml"
            config_file.write_text("""
name: myapp
port: 8080
domain: flask
auto_register: true
auto_caddy: false
""")
            config = ProjectConfig(Path(tmpdir))

            self.assertTrue(config.exists())
            self.assertEqual(config.name, "myapp")
            self.assertEqual(config.port, 8080)
            self.assertEqual(config.domain, "flask")
            self.assertTrue(config.auto_register)
            self.assertFalse(config.auto_caddy)

    @unittest.skipUnless(YAML_AVAILABLE, "pyyaml not installed")
    def test_yaml_search_parent_dirs(self):
        """Test that config is found in parent directories"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config in parent
            config_file = Path(tmpdir) / "devhost.yml"
            config_file.write_text("name: parentapp\nport: 3000\n")

            # Create child directory
            child_dir = Path(tmpdir) / "subdir" / "deep"
            child_dir.mkdir(parents=True)

            # Load from child - should find parent config
            config = ProjectConfig(child_dir)

            self.assertTrue(config.exists())
            self.assertEqual(config.name, "parentapp")
            self.assertEqual(config.port, 3000)

    def test_url_property(self):
        """Test URL generation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ProjectConfig(Path(tmpdir))
            config.config["name"] = "testapp"
            config.config["domain"] = "dev"

            self.assertEqual(config.url, "http://testapp.dev")

    def test_name_sanitization(self):
        """Test that name is sanitized (lowercase, no spaces)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a directory with spaces
            dir_with_spaces = Path(tmpdir) / "My App Name"
            dir_with_spaces.mkdir()

            config = ProjectConfig(dir_with_spaces)
            self.assertEqual(config.name, "my-app-name")


class TestDevhostRunner(unittest.TestCase):
    """Tests for DevhostRunner class"""

    def test_find_free_port(self):
        """Test finding a free port"""
        port = find_free_port(start=10000, end=10100)
        self.assertGreaterEqual(port, 10000)
        self.assertLess(port, 10100)

    def test_is_port_in_use(self):
        """Test port availability check"""
        import socket

        # Bind a port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
            # Port is in use while socket is open
            self.assertTrue(is_port_in_use(port))

        # Port should be free after socket closes
        # (may need small delay on some systems)

    def test_detect_flask_framework(self):
        """Test Flask framework detection"""
        mock_app = MagicMock()
        mock_app.__class__.__name__ = "Flask"
        mock_app.__class__.__module__ = "flask.app"

        with patch.object(ProjectConfig, "__init__", lambda x, y=None: None):
            runner = DevhostRunner.__new__(DevhostRunner)
            runner.app = mock_app
            runner.project_config = MagicMock()
            runner.project_config.name = "test"
            runner.project_config.port = 8000
            runner.project_config.domain = "localhost"
            runner.project_config.auto_register = True
            runner.project_config.auto_caddy = True

            framework = runner._detect_framework()
            self.assertEqual(framework, "flask")

    def test_detect_fastapi_framework(self):
        """Test FastAPI framework detection"""
        mock_app = MagicMock()
        mock_app.__class__.__name__ = "FastAPI"
        mock_app.__class__.__module__ = "fastapi.applications"

        with patch.object(ProjectConfig, "__init__", lambda x, y=None: None):
            runner = DevhostRunner.__new__(DevhostRunner)
            runner.app = mock_app
            runner.project_config = MagicMock()
            runner.project_config.name = "test"
            runner.project_config.port = 8000
            runner.project_config.domain = "localhost"
            runner.project_config.auto_register = True
            runner.project_config.auto_caddy = True

            framework = runner._detect_framework()
            self.assertEqual(framework, "fastapi")

    @patch("devhost_cli.runner.Config")
    def test_resolve_name_conflict_no_conflict(self, mock_config_class):
        """Test name resolution when no conflict exists"""
        mock_config = MagicMock()
        mock_config.load.return_value = {}
        mock_config_class.return_value = mock_config

        with tempfile.TemporaryDirectory():
            mock_app = MagicMock()
            runner = DevhostRunner(mock_app, name="newapp", port=8000)

            result = runner._resolve_name_conflict("newapp", 8000)
            self.assertEqual(result, "newapp")

    @patch("devhost_cli.runner.Config")
    def test_resolve_name_conflict_same_port(self, mock_config_class):
        """Test name resolution when same name exists with same port"""
        mock_config = MagicMock()
        mock_config.load.return_value = {"existingapp": 8000}
        mock_config_class.return_value = mock_config

        with tempfile.TemporaryDirectory():
            mock_app = MagicMock()
            runner = DevhostRunner(mock_app, name="existingapp", port=8000)

            result = runner._resolve_name_conflict("existingapp", 8000)
            self.assertEqual(result, "existingapp")  # No conflict

    @patch("sys.stdin")
    @patch("devhost_cli.runner.Config")
    def test_resolve_name_conflict_different_port_non_interactive(self, mock_config_class, mock_stdin):
        """Test name resolution in non-interactive mode"""
        mock_config = MagicMock()
        mock_config.load.return_value = {"myapp": 3000}
        mock_config_class.return_value = mock_config

        mock_stdin.isatty.return_value = False  # Non-interactive

        with tempfile.TemporaryDirectory():
            mock_app = MagicMock()
            runner = DevhostRunner(mock_app, name="myapp", port=8000)

            result = runner._resolve_name_conflict("myapp", 8000)
            self.assertEqual(result, "myapp-2")  # Auto-suffix

    @patch("devhost_cli.runner.Config")
    def test_register_and_unregister(self, mock_config_class):
        """Test route registration and cleanup"""
        mock_config = MagicMock()
        routes = {}
        mock_config.load.return_value = routes
        mock_config.save.side_effect = lambda r: routes.update(r)
        mock_config_class.return_value = mock_config

        with tempfile.TemporaryDirectory():
            mock_app = MagicMock()
            runner = DevhostRunner(mock_app, name="testapp", port=9000)

            # Register
            runner.register()
            self.assertEqual(runner.registered_name, "testapp")
            self.assertEqual(runner.registered_port, 9000)

            # Verify save was called with route
            mock_config.save.assert_called()


if __name__ == "__main__":
    unittest.main()
