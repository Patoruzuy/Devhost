# Changelog

All notable changes to this project will be documented in this file.

The format is based on "Keep a Changelog" and this project follows
Semantic Versioning.

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
- Legacy bash CLI preserved as `devhost.sh` during migration.

### Changed
- `devhost` now generates Caddyfiles and manages hosts entries from Python.
- README updated for the Python CLI and installer usage.

### Removed
- Legacy installers and shims (`install.sh`, `setup-macos.sh`, `setup-windows.ps1`, `devhost.ps1`, `devhost.sh`).

### Notes
- See `README.md` for setup and usage instructions.
