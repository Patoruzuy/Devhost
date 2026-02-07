"""Tests for the devhost_tui package (new architecture)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

try:
    from devhost_tui.widgets import DetailsPane, FlowDiagram, IntegrityPanel
except Exception as exc:  # pragma: no cover - optional dependency
    raise unittest.SkipTest("textual is not available") from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeState:
    """Minimal StateConfig stand-in for unit tests."""

    def __init__(self, proxy_mode: str = "gateway", external_driver: str = "caddy"):
        self.proxy_mode = proxy_mode
        self.external_driver = external_driver
        self.system_domain = "localhost"
        self.gateway_port = 7777
        self.external_config_path = None
        self.devhost_dir = Path("~/.devhost")
        self.state_file = Path("~/.devhost/state.yml")
        self.routes = {}
        self._hashes: dict[str, str] = {}

    def set_route(self, name, upstream, domain="localhost", enabled=True, tags=None):
        self.routes[name] = {"upstream": upstream, "domain": domain, "enabled": enabled, "tags": tags or []}

    def remove_route(self, name):
        self.routes.pop(name, None)

    def record_hash(self, path):
        self._hashes[str(path)] = "recorded"

    def remove_hash(self, path):
        self._hashes.pop(str(path), None)

    def check_all_integrity(self):
        return {}

    def replace_state(self, raw):
        pass

    def reload(self):
        pass

    @property
    def raw(self):
        return {
            "proxy": {
                "mode": self.proxy_mode,
                "gateway": {"listen": "127.0.0.1:7777"},
                "system": {"domain": self.system_domain},
            },
            "routes": dict(self.routes),
        }


# ---------------------------------------------------------------------------
# SessionState tests
# ---------------------------------------------------------------------------


class TestSessionState(unittest.TestCase):
    """Test the draft/apply SessionState pattern."""

    def _make_state(self, raw: dict | None = None) -> MagicMock:
        state = MagicMock()
        state.raw = raw or {
            "proxy": {"mode": "gateway", "gateway": {"listen": "127.0.0.1:7777"}, "system": {"domain": "localhost"}},
            "routes": {},
        }
        state.devhost_dir = Path("~/.devhost")
        state.state_file = Path("~/.devhost/state.yml")
        state.check_all_integrity.return_value = {}
        return state

    def test_initial_no_changes(self):
        from devhost_tui.session import SessionState

        session = SessionState(self._make_state())
        self.assertFalse(session.has_changes())

    def test_set_route_marks_dirty(self):
        from devhost_tui.session import SessionState

        session = SessionState(self._make_state())
        session.set_route("api", "127.0.0.1:8000", domain="localhost")
        self.assertTrue(session.has_changes())
        self.assertIn("api", session.routes)

    def test_remove_route(self):
        from devhost_tui.session import SessionState

        raw = {
            "proxy": {"mode": "gateway", "gateway": {"listen": "127.0.0.1:7777"}, "system": {"domain": "localhost"}},
            "routes": {"web": {"upstream": "127.0.0.1:3000", "domain": "localhost", "enabled": True, "tags": []}},
        }
        session = SessionState(self._make_state(raw))
        session.remove_route("web")
        self.assertNotIn("web", session.routes)
        self.assertTrue(session.has_changes())

    def test_reset_clears_changes(self):
        from devhost_tui.session import SessionState

        session = SessionState(self._make_state())
        session.set_route("api", "127.0.0.1:8000", domain="localhost")
        session.reset()
        self.assertFalse(session.has_changes())

    def test_proxy_mode(self):
        from devhost_tui.session import SessionState

        session = SessionState(self._make_state())
        self.assertEqual(session.proxy_mode, "gateway")
        session.set_proxy_mode("system")
        self.assertEqual(session.proxy_mode, "system")

    def test_gateway_port(self):
        from devhost_tui.session import SessionState

        session = SessionState(self._make_state())
        self.assertEqual(session.gateway_port, 7777)

    def test_external_config(self):
        from devhost_tui.session import SessionState

        session = SessionState(self._make_state())
        session.set_external_config("nginx", "/etc/nginx/nginx.conf")
        self.assertEqual(session.external_driver, "nginx")
        self.assertEqual(session.external_config_path, Path("/etc/nginx/nginx.conf"))


# ---------------------------------------------------------------------------
# ProbeService helpers
# ---------------------------------------------------------------------------


class TestProbeServiceHelpers(unittest.TestCase):
    def test_parse_listen_port_with_host(self):
        from devhost_tui.services import ProbeService

        self.assertEqual(ProbeService._parse_listen_port("127.0.0.1:8080", 80), 8080)

    def test_parse_listen_port_bare(self):
        from devhost_tui.services import ProbeService

        self.assertEqual(ProbeService._parse_listen_port("443", 80), 443)

    def test_parse_listen_port_empty(self):
        from devhost_tui.services import ProbeService

        self.assertEqual(ProbeService._parse_listen_port("", 80), 80)

    def test_parse_listen_port_invalid(self):
        from devhost_tui.services import ProbeService

        self.assertEqual(ProbeService._parse_listen_port("abc", 80), 80)

    def test_compute_probe_targets_gateway(self):
        from devhost_tui.services import ProbeService

        targets = ProbeService._compute_probe_targets("gateway", 7777, "127.0.0.1:80", "127.0.0.1:443")
        self.assertEqual(targets, [("http", 7777)])

    def test_compute_probe_targets_system(self):
        from devhost_tui.services import ProbeService

        targets = ProbeService._compute_probe_targets("system", 7777, "127.0.0.1:80", "127.0.0.1:443")
        self.assertEqual(targets, [("https", 443), ("http", 80)])

    def test_compute_probe_targets_off(self):
        from devhost_tui.services import ProbeService

        targets = ProbeService._compute_probe_targets("off", 7777, "127.0.0.1:80", "127.0.0.1:443")
        self.assertEqual(targets, [])

    def test_compute_probe_targets_single_port(self):
        from devhost_tui.services import ProbeService

        targets = ProbeService._compute_probe_targets("system", 7777, "127.0.0.1:8080", "127.0.0.1:8080")
        self.assertEqual(targets, [("https", 8080)])


# ---------------------------------------------------------------------------
# LogTailService helpers
# ---------------------------------------------------------------------------


class TestLogTailServiceHelpers(unittest.TestCase):
    def test_format_lines_no_highlight(self):
        from devhost_tui.services import LogTailService

        result = LogTailService.format_lines(["hello world", "foo bar"])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "hello world")

    def test_format_lines_with_highlight(self):
        from devhost_tui.services import LogTailService

        result = LogTailService.format_lines(["hello world", "foo bar"], highlight="world")
        self.assertIn("[reverse]", result[0])
        self.assertNotIn("[reverse]", result[1])

    def test_format_lines_case_insensitive(self):
        from devhost_tui.services import LogTailService

        result = LogTailService.format_lines(["Hello WORLD"], highlight="world")
        self.assertIn("[reverse]", result[0])


# ---------------------------------------------------------------------------
# PortScanCache
# ---------------------------------------------------------------------------


class TestPortScanCache(unittest.TestCase):
    def test_initial_is_stale(self):
        from devhost_tui.services import PortScanCache

        cache = PortScanCache(MagicMock())
        self.assertTrue(cache.is_stale)

    def test_get_results_empty(self):
        from devhost_tui.services import PortScanCache

        cache = PortScanCache(MagicMock())
        ports, in_progress = cache.get_results()
        self.assertEqual(ports, [])
        self.assertTrue(in_progress)


# ---------------------------------------------------------------------------
# NavSidebar message
# ---------------------------------------------------------------------------


class TestNavSidebarMessage(unittest.TestCase):
    def test_screen_selected(self):
        from devhost_tui.widgets import NavSidebar

        msg = NavSidebar.ScreenSelected("tunnels")
        self.assertEqual(msg.screen_id, "tunnels")


# ---------------------------------------------------------------------------
# CommandProvider
# ---------------------------------------------------------------------------


class TestDevhostCommandProvider(unittest.TestCase):
    def test_build_commands(self):
        from devhost_tui.commands import DevhostCommandProvider

        provider = DevhostCommandProvider.__new__(DevhostCommandProvider)
        app = MagicMock()
        commands = provider._build_commands(app)
        self.assertIsInstance(commands, list)
        self.assertGreaterEqual(len(commands), 15)
        for name, help_text, callback in commands:
            self.assertIsInstance(name, str)
            self.assertIsInstance(help_text, str)
            self.assertTrue(callable(callback))


# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------


class TestMessageTypes(unittest.TestCase):
    def test_state_file_changed(self):
        from devhost_tui.services import StateFileChanged

        msg = StateFileChanged()
        self.assertIsNotNone(msg)

    def test_probe_complete(self):
        from devhost_tui.services import ProbeComplete

        msg = ProbeComplete({"api": {"upstream_ok": True}})
        self.assertEqual(msg.results["api"]["upstream_ok"], True)

    def test_port_scan_complete(self):
        from devhost_tui.services import PortScanComplete

        msg = PortScanComplete([])
        self.assertEqual(msg.ports, [])


# ---------------------------------------------------------------------------
# CLI Bridge imports
# ---------------------------------------------------------------------------


class TestCliBridgeImports(unittest.TestCase):
    def test_imports(self):
        from devhost_tui.cli_bridge import (
            DiagnosticsBridge,
            FeaturesBridge,
            ProxyBridge,
            RouterBridge,
            ScannerBridge,
            TunnelBridge,
        )

        for cls in [RouterBridge, TunnelBridge, ProxyBridge, FeaturesBridge, DiagnosticsBridge, ScannerBridge]:
            self.assertTrue(callable(cls))


# ---------------------------------------------------------------------------
# Screen imports
# ---------------------------------------------------------------------------


class TestScreenImports(unittest.TestCase):
    def test_imports(self):
        from devhost_tui.screens import (
            DiagnosticsScreen,
            ProxyScreen,
            RoutesScreen,
            SettingsScreen,
            TunnelsScreen,
        )

        for cls in [RoutesScreen, TunnelsScreen, ProxyScreen, DiagnosticsScreen, SettingsScreen]:
            self.assertTrue(callable(cls))


# ---------------------------------------------------------------------------
# App import + keybinding policy
# ---------------------------------------------------------------------------


class TestAppImport(unittest.TestCase):
    def test_import(self):
        from devhost_tui.app import DevhostDashboard, run_dashboard

        self.assertTrue(callable(DevhostDashboard))
        self.assertTrue(callable(run_dashboard))

    def test_bindings_use_modifiers(self):
        """Bare single-letter keys (except q) must not be in BINDINGS."""
        from devhost_tui.app import DevhostDashboard

        bare = set()
        for b in DevhostDashboard.BINDINGS:
            key = b.key if hasattr(b, "key") else b[0]
            if key == "q":
                continue
            if len(key) == 1 and key.isalpha():
                bare.add(key)
        self.assertEqual(bare, set(), f"Bare keys without modifiers: {bare}")


# ---------------------------------------------------------------------------
# Wizard tests (enhanced wizard in wizard.py)
# ---------------------------------------------------------------------------


class StubInput:
    def __init__(self, value: str):
        self.value = value


class WizardTests(unittest.TestCase):
    def _make_wizard(self):
        from devhost_tui.wizard import AddRouteWizard

        class Harness(AddRouteWizard):
            def __init__(self):
                super().__init__()
                self._app = SimpleNamespace(
                    notify=Mock(),
                    refresh_data=Mock(),
                    queue_route_change=Mock(),
                    get_port_scan_results=Mock(return_value=([], False)),
                )
                self._query = {}

            @property
            def app(self):
                return self._app

            @app.setter
            def app(self, val):
                self._app = val

            def query_one(self, sel, expect_type=None):
                return self._query[sel]

        return Harness()

    def test_apply_gateway(self):
        w = self._make_wizard()
        w.route_name = "api"
        w.route_upstream = "127.0.0.1:8000"
        w.route_mode = "gateway"
        w._apply_route()
        w.app.queue_route_change.assert_called_once_with("api", "127.0.0.1:8000", "gateway")

    def test_apply_external(self):
        w = self._make_wizard()
        w.route_name = "api"
        w.route_upstream = "127.0.0.1:8000"
        w.route_mode = "external"
        w._apply_route()
        w.app.queue_route_change.assert_called_once_with("api", "127.0.0.1:8000", "external")


# ---------------------------------------------------------------------------
# Modals cleanup
# ---------------------------------------------------------------------------


class TestModalsCleanup(unittest.TestCase):
    def test_no_legacy_wizard_in_modals(self):
        import devhost_tui.modals as modals

        self.assertFalse(hasattr(modals, "AddRouteWizard"))

    def test_wizard_in_wizard_module(self):
        from devhost_tui.wizard import AddRouteWizard

        self.assertTrue(callable(AddRouteWizard))

    def test_kept_modals_exist(self):
        from devhost_tui.modals import (
            ConfirmDeleteModal,
            ConfirmProxyExposeModal,
            ConfirmReloadModal,
            ConfirmResetModal,
            ConfirmRestoreModal,
            DiagnosticsPreviewModal,
            ExternalProxyModal,
            HelpModal,
            IntegrityDiffModal,
            ProxyExposeModal,
            QRCodeModal,
        )

        for cls in [
            ExternalProxyModal,
            DiagnosticsPreviewModal,
            QRCodeModal,
            IntegrityDiffModal,
            ConfirmRestoreModal,
            ConfirmReloadModal,
            ConfirmProxyExposeModal,
            ProxyExposeModal,
            ConfirmResetModal,
            HelpModal,
            ConfirmDeleteModal,
        ]:
            self.assertTrue(callable(cls))


# ---------------------------------------------------------------------------
# Dead files
# ---------------------------------------------------------------------------


class TestDeadFilesRemoved(unittest.TestCase):
    def test_no_state_manager(self):
        path = Path(__file__).parent.parent / "devhost_tui" / "state_manager.py"
        self.assertFalse(path.exists(), "state_manager.py should be deleted")

    def test_no_actions(self):
        path = Path(__file__).parent.parent / "devhost_tui" / "actions.py"
        self.assertFalse(path.exists(), "actions.py should be deleted")

    def test_no_event_handlers(self):
        path = Path(__file__).parent.parent / "devhost_tui" / "event_handlers.py"
        self.assertFalse(path.exists(), "event_handlers.py should be deleted")

    def test_no_workers(self):
        path = Path(__file__).parent.parent / "devhost_tui" / "workers.py"
        self.assertFalse(path.exists(), "workers.py should be deleted")


# ---------------------------------------------------------------------------
# Integrity resolution (app method)
# ---------------------------------------------------------------------------


class TestIntegrityResolve(unittest.TestCase):
    def test_accept_records_hash(self):
        from devhost_tui.app import DevhostDashboard

        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b"data")
        tmp.close()
        try:
            state = MagicMock()
            state.check_all_integrity.return_value = {}
            fake = SimpleNamespace(
                state=state,
                _integrity_results=None,
                notify=Mock(),
                refresh_data=Mock(),
            )
            DevhostDashboard.resolve_integrity(fake, tmp.name, "accept")
            state.record_hash.assert_called_once_with(Path(tmp.name))
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    def test_ignore_removes_hash(self):
        from devhost_tui.app import DevhostDashboard

        state = MagicMock()
        state.check_all_integrity.return_value = {}
        fake = SimpleNamespace(
            state=state,
            _integrity_results=None,
            notify=Mock(),
            refresh_data=Mock(),
        )
        DevhostDashboard.resolve_integrity(fake, "/tmp/test.conf", "ignore")
        state.remove_hash.assert_called_once_with(Path("/tmp/test.conf"))


# ---------------------------------------------------------------------------
# DetailsPane verify content tests
# ---------------------------------------------------------------------------


class TestDetailsPaneVerify(unittest.TestCase):
    """Test DetailsPane.show_route populates verify/config tabs."""

    def _stub_details(self):
        class StubVerify:
            def __init__(self):
                self.text = ""

            def update(self, text):
                self.text = text

        class StubDetails(DetailsPane):
            def __init__(self):
                super().__init__()
                self._verify = StubVerify()

            def query_one(self, selector, expect_type=None):
                if selector == "#verify-content":
                    return self._verify
                if selector == "#flow-content":
                    return SimpleNamespace(update=lambda *a, **k: None)
                if selector == "#config-content":
                    return SimpleNamespace(update=lambda *a, **k: None)
                if selector == FlowDiagram:
                    return SimpleNamespace(show_flow=lambda *a, **k: None)
                if selector == IntegrityPanel:
                    return SimpleNamespace(update_integrity=lambda *a, **k: None)
                return SimpleNamespace(update=lambda *a, **k: None)

        return StubDetails()

    def test_integrity_drift_shown(self):
        details = self._stub_details()
        route = {"upstream": "127.0.0.1:8000", "domain": "localhost", "enabled": True}
        state = FakeState()
        probes = {"api": {"route_ok": True, "upstream_ok": True, "latency_ms": 1, "checked_at": "now"}}
        integrity = {"file": (False, "modified")}
        details.show_route("api", route, state, probes, integrity)
        self.assertIn("Integrity: DRIFT", details._verify.text)

    def test_probe_error_shown(self):
        details = self._stub_details()
        route = {"upstream": "127.0.0.1:8000", "domain": "localhost", "enabled": True}
        state = FakeState()
        probes = {
            "api": {
                "route_ok": False,
                "upstream_ok": False,
                "latency_ms": 1,
                "checked_at": "now",
                "route_error": "HTTP 502",
                "upstream_error": "TCP connect failed",
            }
        }
        details.show_route("api", route, state, probes, {})
        self.assertIn("Route Error: HTTP 502", details._verify.text)
        self.assertIn("Upstream Error: TCP connect failed", details._verify.text)


# ---------------------------------------------------------------------------
# queue_route_change
# ---------------------------------------------------------------------------


class TestQueueRouteChange(unittest.TestCase):
    def test_stages_draft(self):
        from devhost_tui.app import DevhostDashboard

        session = MagicMock()
        session.system_domain = "localhost"
        session.external_driver = "caddy"
        fake = SimpleNamespace(
            session=session,
            notify=Mock(),
            refresh_data=Mock(),
        )
        DevhostDashboard.queue_route_change(fake, "api", "127.0.0.1:8000", "gateway")
        session.set_route.assert_called_once()
        session.set_proxy_mode.assert_called_once_with("gateway")


if __name__ == "__main__":
    unittest.main()
