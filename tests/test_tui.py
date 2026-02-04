"""Tests for TUI flows (wizard + delete)."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

try:
    from devhost_tui.app import DevhostDashboard
    from devhost_tui.modals import AddRouteWizard
except Exception as exc:  # pragma: no cover - optional dependency
    raise unittest.SkipTest("textual is not available") from exc


class StubInput:
    def __init__(self, value: str):
        self.value = value


class StubRadioSet:
    def __init__(self, button_id: str | None):
        self.pressed_button = SimpleNamespace(id=button_id) if button_id else None


class FakeState:
    def __init__(self, proxy_mode: str = "gateway", external_driver: str = "nginx"):
        self.proxy_mode = proxy_mode
        self.external_driver = external_driver
        self.system_domain = "localhost"
        self.gateway_port = 7777
        self.removed = None
        self.set_external_driver = None
        self.routes = {}

    def set_route(self, name, upstream, domain, enabled=True):
        self.routes[name] = {
            "upstream": upstream,
            "domain": domain,
            "enabled": enabled,
        }

    def remove_route(self, name):
        self.removed = name
        self.routes.pop(name, None)

    def set_external_config(self, driver, config_path=None):
        self.set_external_driver = driver


class WizardHarness(AddRouteWizard):
    def __init__(self):
        super().__init__()
        self._app = SimpleNamespace(notify=Mock(), refresh_data=Mock())
        self._query = {}

    @property
    def app(self):
        return self._app

    @app.setter
    def app(self, value):
        self._app = value

    def query_one(self, selector, expect_type=None):  # type: ignore[override]
        return self._query[selector]


class WizardTests(unittest.TestCase):
    def test_wizard_rejects_invalid_name(self):
        wizard = WizardHarness()
        wizard.step = 0
        wizard._query = {
            "#name-input": StubInput("bad_name"),
            "#upstream-input": StubInput("8000"),
        }

        wizard._advance_step()

        self.assertEqual(wizard.step, 0)
        wizard.app.notify.assert_called()
        msg = wizard.app.notify.call_args[0][0]
        self.assertIn("Invalid route name", msg)

    def test_wizard_rejects_invalid_upstream(self):
        wizard = WizardHarness()
        wizard.step = 0
        wizard._query = {
            "#name-input": StubInput("api"),
            "#upstream-input": StubInput("not-a-target"),
        }

        wizard._advance_step()

        self.assertEqual(wizard.step, 0)
        wizard.app.notify.assert_called()
        msg = wizard.app.notify.call_args[0][0]
        self.assertIn("Invalid upstream target", msg)

    def test_wizard_apply_system_mode(self):
        wizard = WizardHarness()
        wizard.route_name = "api"
        wizard.route_upstream = "127.0.0.1:8000"
        wizard.route_mode = "system"
        fake_state = FakeState()

        with patch("devhost_tui.modals.StateConfig", return_value=fake_state):
            with patch("devhost_cli.caddy_lifecycle.write_system_caddyfile") as write_caddy:
                wizard._apply_route()

        self.assertEqual(fake_state.proxy_mode, "system")
        write_caddy.assert_called_once_with(fake_state)

    def test_wizard_apply_external_mode(self):
        wizard = WizardHarness()
        wizard.route_name = "api"
        wizard.route_upstream = "127.0.0.1:8000"
        wizard.route_mode = "external"
        fake_state = FakeState(proxy_mode="gateway", external_driver="nginx")

        with patch("devhost_tui.modals.StateConfig", return_value=fake_state):
            with patch("devhost_cli.proxy.export_snippets") as export_snippets:
                wizard._apply_route()

        self.assertEqual(fake_state.proxy_mode, "external")
        self.assertEqual(fake_state.set_external_driver, "nginx")
        export_snippets.assert_called_once_with(fake_state, ["nginx"])


class DashboardDeleteTests(unittest.TestCase):
    def test_delete_route_regenerates_system_config(self):
        fake_state = FakeState(proxy_mode="system")
        fake_self = SimpleNamespace(
            selected_route="api",
            state=fake_state,
            notify=Mock(),
            refresh_data=Mock(),
        )

        with patch("devhost_cli.caddy_lifecycle.write_system_caddyfile") as write_caddy:
            DevhostDashboard.action_delete_route(fake_self)

        self.assertEqual(fake_state.removed, "api")
        write_caddy.assert_called_once_with(fake_state)

    def test_delete_route_regenerates_external_snippet(self):
        fake_state = FakeState(proxy_mode="external", external_driver="nginx")
        fake_self = SimpleNamespace(
            selected_route="api",
            state=fake_state,
            notify=Mock(),
            refresh_data=Mock(),
        )

        with patch("devhost_cli.proxy.export_snippets") as export_snippets:
            DevhostDashboard.action_delete_route(fake_self)

        self.assertEqual(fake_state.removed, "api")
        export_snippets.assert_called_once_with(fake_state, ["nginx"])


if __name__ == "__main__":
    unittest.main()
