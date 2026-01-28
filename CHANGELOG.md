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

### Notes
- See `README.md` for setup and usage instructions.
