"""Tests for TUI flows (wizard + delete)."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

try:
    from devhost_tui.app import DevhostDashboard
    from devhost_tui.modals import AddRouteWizard, ExternalProxyModal
    from devhost_tui.widgets import DetailsPane, FlowDiagram, IntegrityPanel
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


class FakeSession(FakeState):
    def __init__(self, proxy_mode: str = "gateway", external_driver: str = "nginx"):
        super().__init__(proxy_mode=proxy_mode, external_driver=external_driver)

    def has_changes(self):
        return True

    def reset(self):
        return None


class WizardHarness(AddRouteWizard):
    def __init__(self):
        super().__init__()
        self._app = SimpleNamespace(notify=Mock(), refresh_data=Mock(), queue_route_change=Mock())
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
        wizard._apply_route()
        wizard.app.queue_route_change.assert_called_once_with("api", "127.0.0.1:8000", "system")

    def test_wizard_apply_external_mode(self):
        wizard = WizardHarness()
        wizard.route_name = "api"
        wizard.route_upstream = "127.0.0.1:8000"
        wizard.route_mode = "external"
        wizard._apply_route()
        wizard.app.queue_route_change.assert_called_once_with("api", "127.0.0.1:8000", "external")


class DashboardDeleteTests(unittest.TestCase):
    def test_delete_route_regenerates_system_config(self):
        fake_state = FakeState(proxy_mode="system")
        fake_session = FakeSession(proxy_mode="system")
        fake_self = SimpleNamespace(
            selected_route="api",
            state=fake_state,
            session=fake_session,
            _probe_results={},
            _log_buffers={},
            notify=Mock(),
            refresh_data=Mock(),
        )
        DevhostDashboard.action_delete_route(fake_self)
        self.assertEqual(fake_session.removed, "api")

    def test_delete_route_regenerates_external_snippet(self):
        fake_state = FakeState(proxy_mode="external", external_driver="nginx")
        fake_session = FakeSession(proxy_mode="external", external_driver="nginx")
        fake_self = SimpleNamespace(
            selected_route="api",
            state=fake_state,
            session=fake_session,
            _probe_results={},
            _log_buffers={},
            notify=Mock(),
            refresh_data=Mock(),
        )
        DevhostDashboard.action_delete_route(fake_self)
        self.assertEqual(fake_session.removed, "api")


class ProbeTargetTests(unittest.TestCase):
    def test_probe_targets_gateway(self):
        targets = DevhostDashboard._compute_probe_targets("gateway", 7777, "127.0.0.1:80", "127.0.0.1:443")
        self.assertEqual(targets, [("http", 7777)])

    def test_probe_targets_system_https_first(self):
        targets = DevhostDashboard._compute_probe_targets("system", 7777, "127.0.0.1:80", "127.0.0.1:443")
        self.assertEqual(targets, [("https", 443), ("http", 80)])

    def test_probe_targets_single_port(self):
        targets = DevhostDashboard._compute_probe_targets("system", 7777, "127.0.0.1:8080", "127.0.0.1:8080")
        self.assertEqual(targets, [("https", 8080)])


class LogPathTests(unittest.TestCase):
    def test_log_path_prefers_route_setting(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        try:
            fake_state = FakeState()
            fake_session = FakeSession()
            fake_session.get_route = Mock(return_value={"log_path": tmp.name})
            fake_self = SimpleNamespace(state=fake_state, session=fake_session)
            path = DevhostDashboard._resolve_log_path(fake_self, "api")
            self.assertEqual(str(path), tmp.name)
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    def test_log_path_fallbacks(self):
        fake_state = FakeState()
        fake_session = FakeSession()
        fake_session.get_route = Mock(return_value={})
        fake_state.devhost_dir = Path(tempfile.mkdtemp())
        logs_dir = fake_state.devhost_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "devhost-router.log"
        log_file.write_text("hello", encoding="utf-8")
        fake_self = SimpleNamespace(state=fake_state, session=fake_session)
        path = DevhostDashboard._resolve_log_path(fake_self, "api")
        self.assertEqual(path, log_file)


class IntegritySummaryTests(unittest.TestCase):
    def test_integrity_summary_in_verify(self):
        # Build a minimal DetailsPane with a stub verify widget
        class StubVerify:
            def __init__(self):
                self.text = ""

            def update(self, text):
                self.text = text

        class StubDetails(DetailsPane):
            def __init__(self):
                super().__init__()
                self._verify = StubVerify()

            def query_one(self, selector, expect_type=None):  # type: ignore[override]
                if selector == "#verify-content":
                    return self._verify
                if selector == "#flow-content":
                    return SimpleNamespace(update=lambda *_args, **_kwargs: None)
                if selector == "#config-content":
                    return SimpleNamespace(update=lambda *_args, **_kwargs: None)
                if selector == FlowDiagram:
                    return SimpleNamespace(show_flow=lambda *_args, **_kwargs: None)
                if selector == IntegrityPanel:
                    return SimpleNamespace(update_integrity=lambda *_args, **_kwargs: None)
                return SimpleNamespace(update=lambda *_args, **_kwargs: None)

        details = StubDetails()
        route = {"upstream": "127.0.0.1:8000", "domain": "localhost", "enabled": True}
        state = FakeState()
        probe_results = {"api": {"route_ok": True, "upstream_ok": True, "latency_ms": 1, "checked_at": "now"}}
        integrity_results = {"file": (False, "modified")}
        details.show_route("api", route, state, probe_results, integrity_results)
        self.assertIn("Integrity: DRIFT", details._verify.text)


class ProbeErrorTests(unittest.TestCase):
    def test_probe_error_shows_in_verify(self):
        class StubVerify:
            def __init__(self):
                self.text = ""

            def update(self, text):
                self.text = text

        class StubDetails(DetailsPane):
            def __init__(self):
                super().__init__()
                self._verify = StubVerify()

            def query_one(self, selector, expect_type=None):  # type: ignore[override]
                if selector == "#verify-content":
                    return self._verify
                if selector == "#flow-content":
                    return SimpleNamespace(update=lambda *_args, **_kwargs: None)
                if selector == "#config-content":
                    return SimpleNamespace(update=lambda *_args, **_kwargs: None)
                if selector == FlowDiagram:
                    return SimpleNamespace(show_flow=lambda *_args, **_kwargs: None)
                if selector == IntegrityPanel:
                    return SimpleNamespace(update_integrity=lambda *_args, **_kwargs: None)
                return SimpleNamespace(update=lambda *_args, **_kwargs: None)

        details = StubDetails()
        route = {"upstream": "127.0.0.1:8000", "domain": "localhost", "enabled": True}
        state = FakeState()
        probe_results = {
            "api": {
                "route_ok": False,
                "upstream_ok": False,
                "latency_ms": 1,
                "checked_at": "now",
                "route_error": "HTTP 502",
                "upstream_error": "TCP connect failed",
            }
        }
        details.show_route("api", route, state, probe_results, {})
        self.assertIn("Route Error: HTTP 502", details._verify.text)
        self.assertIn("Upstream Error: TCP connect failed", details._verify.text)


class IntegrityResolveTests(unittest.TestCase):
    def test_resolve_integrity_accept(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b"data")
        tmp.close()
        try:
            fake_state = SimpleNamespace(
                record_hash=Mock(),
                remove_hash=Mock(),
                check_all_integrity=Mock(return_value={}),
            )
            fake_self = SimpleNamespace(
                state=fake_state,
                notify=Mock(),
                _apply_integrity_results=Mock(),
            )
            DevhostDashboard.resolve_integrity(fake_self, tmp.name, "accept")
            fake_state.record_hash.assert_called_once_with(Path(tmp.name))
            fake_self._apply_integrity_results.assert_called_once_with({})
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    def test_resolve_integrity_ignore(self):
        fake_state = SimpleNamespace(
            record_hash=Mock(),
            remove_hash=Mock(),
            check_all_integrity=Mock(return_value={}),
        )
        fake_self = SimpleNamespace(
            state=fake_state,
            notify=Mock(),
            _apply_integrity_results=Mock(),
        )
        DevhostDashboard.resolve_integrity(fake_self, "C:/tmp/example.conf", "ignore")
        fake_state.remove_hash.assert_called_once_with(Path("C:/tmp/example.conf"))
        fake_self._apply_integrity_results.assert_called_once_with({})


class ExternalProxyActionTests(unittest.TestCase):
    def test_action_external_proxy_opens_modal(self):
        fake_self = SimpleNamespace(push_screen=Mock())
        DevhostDashboard.action_external_proxy(fake_self)
        args, _kwargs = fake_self.push_screen.call_args
        self.assertIsInstance(args[0], ExternalProxyModal)


class NextActionTests(unittest.TestCase):
    def test_next_action_apply_when_draft(self):
        fake_session = SimpleNamespace(has_changes=Mock(return_value=True), routes={}, proxy_mode="gateway")
        fake_self = SimpleNamespace(session=fake_session, _integrity_results={}, state=SimpleNamespace(external_config_path=None))
        msg = DevhostDashboard._compute_next_action(fake_self)
        self.assertIn("Apply", msg)

    def test_next_action_add_route_when_empty(self):
        fake_session = SimpleNamespace(has_changes=Mock(return_value=False), routes={}, proxy_mode="gateway")
        fake_self = SimpleNamespace(session=fake_session, _integrity_results={}, state=SimpleNamespace(external_config_path=None))
        msg = DevhostDashboard._compute_next_action(fake_self)
        self.assertIn("Add your first route", msg)

    def test_next_action_integrity_drift(self):
        fake_session = SimpleNamespace(has_changes=Mock(return_value=False), routes={"api": {}}, proxy_mode="gateway")
        fake_self = SimpleNamespace(
            session=fake_session,
            _integrity_results={"file": (False, "modified")},
            state=SimpleNamespace(external_config_path=None),
        )
        msg = DevhostDashboard._compute_next_action(fake_self)
        self.assertIn("Resolve integrity drift", msg)

    def test_next_action_external_attach(self):
        fake_session = SimpleNamespace(has_changes=Mock(return_value=False), routes={"api": {}}, proxy_mode="external")
        fake_self = SimpleNamespace(session=fake_session, _integrity_results={}, state=SimpleNamespace(external_config_path=None))
        msg = DevhostDashboard._compute_next_action(fake_self)
        self.assertIn("Attach external proxy", msg)


if __name__ == "__main__":
    unittest.main()
