# Changelog

All notable changes to this project will be documented in this file.

The format is based on "Keep a Changelog" and this project follows
Semantic Versioning.

## [Unreleased]
### Added
- `devhost fix-http` to convert `https://` mappings back to `http://`.
- `devhost.ps1` PowerShell shim for easier Windows invocation.
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

### Fixed
- Windows elevation relaunch now passes `--elevated` before the subcommand.
- CLI list/url/open no longer fail due to missing methods or Unicode output.
- Docker healthcheck added for better container monitoring.

## [1.0.0] - 2026-01-28
### Added
- Initial public release: `v1.0.0`.
- `router` service: FastAPI-based wildcard reverse proxy with improved
  forwarding of status codes, headers, and binary bodies.
- `devhost` CLI: unified Caddyfile generation with `jq`/Python fallback
  and port validation.
- `install.sh`: safer DNS/resolv.conf guidance and Debian/Ubuntu install
  steps for dependencies.
- GitHub Actions CI workflow for Python syntax checks.

### Fixed
- Proxy: preserve query strings and filter hop-by-hop headers.
- Router: load `devhost.json` per-request so CLI changes take effect
  without restarting.

## [2.0.0] - 2026-01-31
### Added
- Python-based `devhost` CLI (cross-platform) with Windows auto-elevation.
- `devhost install` (Python) plus `install.py` wrapper for a single entrypoint.
- Windows Caddy install/start/stop helpers in the Python CLI.
- Router metrics endpoints (`/metrics`, `/routes`) and request logging controls.

### Changed
- `devhost` now generates Caddyfiles and manages hosts entries from Python.
- README updated for the Python CLI and installer usage.

### Removed
- Legacy installers and shims (`install.sh`, `setup-macos.sh`, `setup-windows.ps1`, `devhost.sh`).

### Notes
- See `README.md` for setup and usage instructions.
