# Changelog

All notable changes to this project will be documented in this file.

The format is based on "Keep a Changelog" and this project follows
Semantic Versioning.

## [Unreleased]
### Added
- (nothing yet)

## [3.0.0-alpha.1] - 2026-02-05
### Added
- **v3 proxy modes** backed by `~/.devhost/state.yml`: `off`, `gateway`, `system`, `external`.
- **External proxy integration**: `devhost proxy export|discover|attach|detach|transfer` for Caddy/nginx/Traefik.
- **System mode Caddy lifecycle**: `devhost proxy upgrade --to system`, start/stop/reload, PID tracking, port-conflict guidance.
- **Gateway router management**: `devhost start|stop|status` with PID/log files under `~/.devhost/` (and `$TEMP`/`/tmp` logs).
- **TUI dashboard** (`devhost dashboard`) built on Textual (optional extra: `devhost[tui]`).
- **Integrity hashing** and drift detection (`devhost integrity`) with backup helpers in state.
- **Tunnel helpers**: `devhost tunnel start|stop|status` (cloudflared/ngrok/localtunnel).
- **Developer utilities**: `devhost logs`, `devhost qr`, `devhost oauth`, `devhost env sync`.
- `devhost fix-http` to convert `https://` mappings back to `http://`.
- `devhost.ps1` PowerShell shim for easier Windows invocation.

### Changed
- Default route config is user-owned: `~/.devhost/devhost.json` (with best-effort migration from legacy locations).
- Copilot + docs guidance updated for the v3 architecture and mode model.

### Removed
- Unused `click` / `rich-click` dependencies (CLI is `argparse`; dashboard is Textual).

### Security
- Router SSRF protection blocks cloud metadata endpoints and private networks by default (opt-in via `DEVHOST_ALLOW_PRIVATE_NETWORKS=1`).

## [2.3.0] - 2026-02-02
### Added
- **Zero-Config Runner** - Run apps with auto-registration:
  - `DevhostRunner` class for unified app running
  - Framework detection (Flask, FastAPI, Django, WSGI)
  - Auto-registration to devhost.json on startup
  - Cleanup on app exit
- **devhost.yml** - Per-project configuration support:
  - `ProjectConfig` class for YAML config loading
  - Configurable name, port, domain, auto_register, auto_caddy
- **Framework wrappers** for one-line usage:
  - `run_flask(app, name="myapp")` with Flask-SocketIO support
  - `run_fastapi(app, name="api")` with uvicorn
  - `run_django("project.wsgi.application", name="admin")`
- **`devhost init` CLI command** - Interactive project setup
- **Conflict resolution** - Prompts user or auto-suffixes (e.g., myapp-2)
- **pyyaml optional dependency** (`pip install devhost[yaml]`)
- 13 new tests for runner functionality (54 total)

### Changed
- README reorganized with Zero-Config Runner as primary use case
- ROADMAP updated with Phase 7 completion

## [2.2.1] - 2026-02-01
### Fixed
- Flask optional dependency relaxed to `>=2.0` (was `>=3.0`)
- Django optional dependency relaxed to `>=4.0` (was `>=5.0`)
- CI workflow now installs dev dependencies correctly

## [2.2.0] - 2026-02-01
### Added
- **WSGI middleware** (`DevhostWSGIMiddleware`) for Flask/Django
- Flask example (`examples/example_flask.py`)
- Django example (`examples/example_django.py`)
- 14 new WSGI tests (41 total tests)
- Flask/Django optional dependencies in pyproject.toml

## [2.1.0] - 2026-01-31
### Added
- **PyPI package published**: `pip install devhost`
- ASGI middleware (`DevhostMiddleware`) for FastAPI/Starlette
- Factory functions (`create_devhost_app`, `enable_subdomain_routing`)
- GitHub Actions workflow for automated PyPI publishing
- Router refactored into 4 modules (cache, core, metrics, utils)
- 65 tests passing

## [2.0.0] - 2026-01-31
### Added
- Modular `devhost_cli` package with 11 separate modules for better maintainability.
- Integration tests for both router and CLI (19 tests total).
- Request ID tracking (UUID-based) with X-Request-ID header for debugging.
- Remote IP support - map domains to devices on your network (e.g., Raspberry Pi).
- Comprehensive troubleshooting documentation in README.
- Windows hosts file behavior documentation with admin elevation requirements.
- Remote IP examples in README (Raspberry Pi, NAS, Docker containers).
- Caddy template now uses file-based `Caddyfile.template` instead of inline string.
- `DEVHOST_CONFIG` environment variable support in CLI Config class.

### Changed
- Wildcard Caddy vhost now defaults to HTTP-only (HTTPS is per-mapping with `--https`).
- CLI output uses ASCII-safe symbols for Windows terminals.
- Refactored monolithic 1412-line CLI script into organized package structure.
- Dependencies pinned with ~= for patch-level flexibility.
- Python 3.10 added to CI test matrix (3.10, 3.11, 3.12).
- Ruff linting enforced in CI with --fix option.
- Python-based `devhost` CLI (cross-platform) with Windows auto-elevation.
- `devhost install` (Python) plus `install.py` wrapper for a single entrypoint.
- Windows Caddy install/start/stop helpers in the Python CLI.
- `devhost` now generates Caddyfiles and manages hosts entries from Python.
- README updated for the Python CLI and installer usage.

### Fixed
- Windows elevation relaunch now passes `--elevated` before the subcommand.
- CLI list/url/open no longer fail due to missing methods or Unicode output.
- Docker healthcheck added for better container monitoring.

### Removed
- Legacy installers and shims (`install.sh`, `setup-macos.sh`, `setup-windows.ps1`, `devhost.sh`).

### Notes
- See `README.md` for setup and usage instructions.
