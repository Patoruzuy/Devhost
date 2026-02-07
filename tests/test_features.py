"""Tests for developer features."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from devhost_cli.features import get_oauth_uris, show_qr_for_route, sync_env_file


class FeatureTests(unittest.TestCase):
    def test_get_oauth_uris_uses_scheme(self):
        uris = get_oauth_uris("app", "example.test", scheme="https")
        self.assertTrue(all(uri.startswith("https://app.example.test") for uri in uris))
        self.assertIn("https://app.example.test/callback", uris)

        uris_with_port = get_oauth_uris("app", "example.test", port=7777, scheme="https")
        self.assertTrue(all(uri.startswith("https://app.example.test:7777") for uri in uris_with_port))
        self.assertIn("https://app.example.test:7777/callback", uris_with_port)

    def test_show_qr_for_route_uses_scheme(self):
        captured = {}

        def fake_generate_qr_code(url, quiet=False):
            captured["url"] = url
            return "QR"

        with patch("devhost_cli.features.Config") as mock_config:
            mock_config.return_value.load.return_value = {"myapp": "https://127.0.0.1:8443"}
            with patch("devhost_cli.features.get_lan_ip", return_value="192.168.1.5"):
                with patch("devhost_cli.features.generate_qr_code", side_effect=fake_generate_qr_code):
                    with patch("devhost_cli.features.console.print"):
                        success = show_qr_for_route("myapp")

        self.assertTrue(success)
        self.assertEqual(captured.get("url"), "https://192.168.1.5:8443")

    def test_sync_env_file_uses_scheme(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "APP_URL=http://old",
                        "ALLOWED_HOSTS=old",
                        "BASE_URL=http://old",
                        "OTHER=keep",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch("devhost_cli.features.Config") as mock_config:
                mock_config.return_value.load.return_value = {"myapp": "https://127.0.0.1:8443"}
                mock_config.return_value.get_domain.return_value = "dev.local"
                with patch("devhost_cli.features.StateConfig") as mock_state:
                    state = mock_state.return_value
                    state.proxy_mode = "system"
                    state.gateway_port = 7777
                    with patch("devhost_cli.features.console.print"):
                        success = sync_env_file("myapp", env_file=str(env_path))

            self.assertTrue(success)
            data = {}
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                data[key] = value.strip().strip('"').strip("'")

            self.assertEqual(data["APP_URL"], "https://myapp.dev.local")
            self.assertEqual(data["BASE_URL"], "https://myapp.dev.local")
            self.assertEqual(data["ALLOWED_HOSTS"], "myapp.dev.local")
            self.assertEqual(data["OTHER"], "keep")


if __name__ == "__main__":
    unittest.main()
