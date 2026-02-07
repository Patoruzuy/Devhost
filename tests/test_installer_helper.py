"""Tests for installer helper and install workflow wiring."""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from devhost_cli import installer
from devhost_cli import main as cli_main


class TestInstallerWorkflow(unittest.TestCase):
    def test_install_shim_exists_and_imports_package_installer(self):
        shim = Path("install.py")
        self.assertTrue(shim.exists(), "install.py shim must exist for compatibility")
        content = shim.read_text(encoding="utf-8")
        self.assertIn("from devhost_cli.installer import main", content)

    def test_cli_install_delegates_to_package_installer(self):
        fake_cli = Mock()
        with (
            patch("devhost_cli.main.DevhostCLI", return_value=fake_cli),
            patch("devhost_cli.installer.main", return_value=0) as installer_main,
            patch("sys.argv", ["devhost", "install", "--dry-run", "--install-completions"]),
        ):
            code = cli_main.main()

        self.assertEqual(code, 0)
        installer_main.assert_called_once_with(["--dry-run", "--install-completions"])

    def test_make_start_depends_on_install(self):
        makefile = Path("Makefile").read_text(encoding="utf-8")
        self.assertIn("start: install", makefile)


class TestInstallerHelper(unittest.TestCase):
    def test_run_cmd_dry_run_skips_subprocess(self):
        with patch("devhost_cli.installer.subprocess.run") as run:
            ok = installer._run_cmd(["echo", "hi"], dry_run=True, assume_yes=True)
        self.assertTrue(ok)
        run.assert_not_called()

    def test_main_dry_run_completions(self):
        code = installer.main(["--dry-run", "--install-completions"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
