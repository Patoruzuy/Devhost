import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

from devhost_cli.cli import DevhostCLI
from devhost_cli.diagnostics import export_diagnostic_bundle, parse_size_limit, preview_diagnostic_bundle


def test_export_diagnostic_bundle_creates_zip(tmp_path: Path):
    devhost_dir = tmp_path / ".devhost"
    devhost_dir.mkdir()

    state_file = devhost_dir / "state.yml"
    state_file.write_text("state: 1", encoding="utf-8")

    proxy_dir = devhost_dir / "proxy" / "caddy"
    proxy_dir.mkdir(parents=True)
    (proxy_dir / "devhost.caddy").write_text("# snippet", encoding="utf-8")

    logs_dir = devhost_dir / "logs"
    logs_dir.mkdir()
    (logs_dir / "app.log").write_text("log", encoding="utf-8")

    log_path = devhost_dir / "router.log"
    log_path.write_text("router", encoding="utf-8")

    config_file = devhost_dir / "devhost.json"
    config_file.write_text("{}", encoding="utf-8")
    domain_file = devhost_dir / "domain"
    domain_file.write_text("local", encoding="utf-8")

    fake_state = SimpleNamespace(devhost_dir=devhost_dir, state_file=state_file)

    success, bundle_path, _manifest = export_diagnostic_bundle(
        fake_state,
        config_file=config_file,
        domain_file=domain_file,
        log_path=log_path,
    )

    assert success is True
    assert bundle_path is not None
    assert bundle_path.exists()

    with zipfile.ZipFile(bundle_path, "r") as zipf:
        names = set(zipf.namelist())
        assert "state/state.yml" in names
        assert "config/devhost.json" in names
        assert "config/domain" in names
        assert "logs/router.log" in names
        assert "proxy/caddy/devhost.caddy" in names
    assert "manifest.json" in names


def test_preview_diagnostic_bundle_counts(tmp_path: Path):
    devhost_dir = tmp_path / ".devhost"
    devhost_dir.mkdir()
    state_file = devhost_dir / "state.yml"
    state_file.write_text("state: 1", encoding="utf-8")
    log_path = devhost_dir / "router.log"
    log_path.write_text("token=abc", encoding="utf-8")
    fake_state = SimpleNamespace(devhost_dir=devhost_dir, state_file=state_file)
    preview = preview_diagnostic_bundle(
        fake_state,
        log_path=log_path,
        include_config=False,
        include_proxy=False,
        include_logs=True,
        redact=True,
    )
    assert preview["total_size"] > 0
    assert preview["redacted_count"] >= 1
    assert preview["included_sorted"][0]["size"] >= preview["included_sorted"][-1]["size"]


def test_diagnostics_upload_uses_tempdir(tmp_path: Path, monkeypatch):
    calls = {}

    def fake_export(state, output_path=None, **_kwargs):
        calls["output_path"] = output_path
        return True, Path(output_path) / "bundle.zip", {"included": [], "missing": []}

    import tempfile

    import devhost_cli.diagnostics as diagnostics_module

    monkeypatch.setattr(diagnostics_module, "export_diagnostic_bundle", fake_export)
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

    cli = DevhostCLI()
    assert cli.diagnostics_upload(redact=True) is True
    assert calls["output_path"] == Path(tmp_path) / "devhost-diagnostics"


def test_export_diagnostic_bundle_respects_output_path(tmp_path: Path):
    devhost_dir = tmp_path / ".devhost"
    devhost_dir.mkdir()
    state_file = devhost_dir / "state.yml"
    state_file.write_text("state: 1", encoding="utf-8")
    out_dir = tmp_path / "out"
    fake_state = SimpleNamespace(devhost_dir=devhost_dir, state_file=state_file)
    success, bundle_path, _manifest = export_diagnostic_bundle(
        fake_state,
        output_path=out_dir,
        include_config=False,
        include_proxy=False,
        include_logs=False,
    )
    assert success is True
    assert bundle_path is not None
    assert bundle_path.parent == out_dir


def test_export_diagnostic_bundle_redacts_logs(tmp_path: Path):
    devhost_dir = tmp_path / ".devhost"
    devhost_dir.mkdir()
    state_file = devhost_dir / "state.yml"
    state_file.write_text("state: 1", encoding="utf-8")
    log_path = devhost_dir / "router.log"
    log_path.write_text("password=supersecret\nAuthorization: Bearer abc123\n", encoding="utf-8")
    fake_state = SimpleNamespace(devhost_dir=devhost_dir, state_file=state_file)
    success, bundle_path, manifest = export_diagnostic_bundle(
        fake_state,
        log_path=log_path,
        include_config=False,
        include_proxy=False,
        include_logs=True,
        redact=True,
    )
    assert success is True
    assert bundle_path is not None
    with zipfile.ZipFile(bundle_path, "r") as zipf:
        content = zipf.read("logs/router.log").decode("utf-8")
    assert "supersecret" not in content
    assert "[REDACTED]" in content
    assert "Authorization: Bearer [REDACTED]" in content
    assert "logs/router.log" in manifest.get("redacted", [])


def test_export_diagnostic_bundle_redacts_headers_and_urls(tmp_path: Path):
    devhost_dir = tmp_path / ".devhost"
    devhost_dir.mkdir()
    state_file = devhost_dir / "state.yml"
    state_file.write_text("state: 1", encoding="utf-8")
    log_path = devhost_dir / "router.log"
    log_path.write_text(
        "Authorization: Basic dXNlcjpwYXNz\n"
        "X-API-Key: superkey\n"
        "DATABASE_PASSWORD=supersecret\n"
        "https://user:pass@localhost:8000/path\n",
        encoding="utf-8",
    )
    fake_state = SimpleNamespace(devhost_dir=devhost_dir, state_file=state_file)
    success, bundle_path, _manifest = export_diagnostic_bundle(
        fake_state,
        log_path=log_path,
        include_config=False,
        include_proxy=False,
        include_logs=True,
        redact=True,
    )
    assert success is True
    assert bundle_path is not None
    with zipfile.ZipFile(bundle_path, "r") as zipf:
        content = zipf.read("logs/router.log").decode("utf-8")
    assert "dXNlcjpwYXNz" not in content
    assert "superkey" not in content
    assert "supersecret" not in content
    assert "user:pass@" not in content
    assert "Authorization: Basic [REDACTED]" in content
    assert "X-API-Key: [REDACTED]" in content
    assert "DATABASE_PASSWORD=[REDACTED]" in content
    assert "https://[REDACTED]@localhost:8000/path" in content


def test_custom_redaction_patterns(tmp_path: Path):
    devhost_dir = tmp_path / ".devhost"
    devhost_dir.mkdir()
    state_file = devhost_dir / "state.yml"
    state_file.write_text("state: 1", encoding="utf-8")
    log_path = devhost_dir / "router.log"
    log_path.write_text("custom_secret=abc123\n", encoding="utf-8")
    redaction_cfg = tmp_path / "redaction.json"
    redaction_cfg.write_text(
        json.dumps(
            {
                "redaction": {
                    "include_defaults": False,
                    "patterns": [
                        {
                            "pattern": "custom_secret=[^\\s]+",
                            "replacement": "custom_secret=[REDACTED]",
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    fake_state = SimpleNamespace(devhost_dir=devhost_dir, state_file=state_file)
    success, bundle_path, manifest = export_diagnostic_bundle(
        fake_state,
        log_path=log_path,
        include_config=False,
        include_proxy=False,
        include_logs=True,
        redact=True,
        redaction_file=redaction_cfg,
    )
    assert success is True
    with zipfile.ZipFile(bundle_path, "r") as zipf:
        content = zipf.read("logs/router.log").decode("utf-8")
    assert "abc123" not in content
    assert "custom_secret=[REDACTED]" in content
    config = manifest.get("redaction_config", {})
    assert config.get("custom_patterns") == 1


def test_export_diagnostic_bundle_size_limit_enforced(tmp_path: Path):
    devhost_dir = tmp_path / ".devhost"
    devhost_dir.mkdir()
    state_file = devhost_dir / "state.yml"
    state_file.write_text("state: 1", encoding="utf-8")
    log_path = devhost_dir / "router.log"
    log_path.write_text("0123456789", encoding="utf-8")
    fake_state = SimpleNamespace(devhost_dir=devhost_dir, state_file=state_file)
    success, bundle_path, manifest = export_diagnostic_bundle(
        fake_state,
        log_path=log_path,
        include_config=False,
        include_proxy=False,
        include_logs=True,
        redact=False,
        size_limit_bytes=5,
    )
    assert success is False
    assert bundle_path is None
    assert "exceeds limit" in manifest.get("error", "")


def test_preview_diagnostic_bundle_over_limit(tmp_path: Path):
    devhost_dir = tmp_path / ".devhost"
    devhost_dir.mkdir()
    state_file = devhost_dir / "state.yml"
    state_file.write_text("state: 1", encoding="utf-8")
    log_path = devhost_dir / "router.log"
    log_path.write_text("0123456789", encoding="utf-8")
    fake_state = SimpleNamespace(devhost_dir=devhost_dir, state_file=state_file)
    preview = preview_diagnostic_bundle(
        fake_state,
        log_path=log_path,
        include_config=False,
        include_proxy=False,
        include_logs=True,
        redact=False,
        size_limit_bytes=5,
    )
    assert preview.get("over_limit") is True
    assert preview.get("size_limit_bytes") == 5


def test_parse_size_limit():
    assert parse_size_limit("50MB") == 50 * 1024 * 1024
    assert parse_size_limit("10kb") == 10 * 1024
    assert parse_size_limit("0") == 0
