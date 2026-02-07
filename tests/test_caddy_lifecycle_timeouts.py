import subprocess
from pathlib import Path


class DummyState:
    def __init__(self):
        self._state = {
            "proxy": {
                "system": {
                    "listen_http": "127.0.0.1:80",
                    "listen_https": "127.0.0.1:443",
                    "caddy_pid": None,
                }
            }
        }
        self.raw = self._state
        self.routes = {}

    def _save(self):
        return None


def _raise_timeout(*args, **kwargs):
    cmd = args[0] if args else kwargs.get("args", "caddy")
    timeout = kwargs.get("timeout", None)
    raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)


def test_start_caddy_timeout_returns_error(monkeypatch, tmp_path: Path):
    import devhost_cli.caddy_lifecycle as caddy

    state = DummyState()
    monkeypatch.setattr(caddy, "find_caddy_executable", lambda: "/usr/bin/caddy")
    monkeypatch.setattr(caddy, "check_port_conflicts", lambda _ports: [])
    monkeypatch.setattr(caddy, "write_system_caddyfile", lambda _state: tmp_path / "Caddyfile")
    monkeypatch.setattr(caddy, "get_caddy_pid", lambda: None)
    monkeypatch.setattr(caddy.subprocess, "run", _raise_timeout)

    success, msg = caddy.start_caddy(state)
    assert success is False
    assert "timed out" in msg.lower()


def test_stop_caddy_timeout_returns_error(monkeypatch):
    import devhost_cli.caddy_lifecycle as caddy

    state = DummyState()
    monkeypatch.setattr(caddy, "find_caddy_executable", lambda: "/usr/bin/caddy")
    monkeypatch.setattr(caddy, "get_caddy_pid", lambda: 4242)
    monkeypatch.setattr(caddy.subprocess, "run", _raise_timeout)

    success, msg = caddy.stop_caddy(state, force=True)
    assert success is False
    assert "timed out" in msg.lower()


def test_reload_caddy_timeout_returns_error(monkeypatch, tmp_path: Path):
    import devhost_cli.caddy_lifecycle as caddy

    state = DummyState()
    monkeypatch.setattr(caddy, "find_caddy_executable", lambda: "/usr/bin/caddy")
    monkeypatch.setattr(caddy, "is_caddy_running", lambda _state: True)
    monkeypatch.setattr(caddy, "get_caddy_pid", lambda: 4242)
    monkeypatch.setattr(caddy, "write_system_caddyfile", lambda _state: tmp_path / "Caddyfile")
    monkeypatch.setattr(caddy.subprocess, "run", _raise_timeout)

    success, msg = caddy.reload_caddy(state)
    assert success is False
    assert "timed out" in msg.lower()
