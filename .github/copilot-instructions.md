# Copilot / AI Agent Instructions for Devhost (v3)

Keep guidance concise and implementation-accurate. Devhost is about **ports + DNS + HTTP(S)/WS proxying**; prefer concrete, verifiable statements over assumptions.

## Architecture (Proxy Modes)

Devhost v3 has **four** proxy modes (stored in `~/.devhost/state.yml`):

1. `off` — no proxy management
2. `gateway` (default) — built-in FastAPI router on a local port (default `7777`)
   - URL pattern: `http://<name>.<domain>:<gateway_port>`
3. `system` — Devhost-managed Caddy on `80/443` (one-time admin setup on Windows)
   - URL pattern: `http(s)://<name>.<domain>` (no port)
4. `external` — integrate with an existing proxy (Caddy/nginx/Traefik); Devhost generates/attaches snippets

## Persistence (What Writes What)

Devhost uses **two** user-owned files under `~/.devhost/`:

- `~/.devhost/devhost.json` — **router input** and mapping source-of-truth (subdomain → target)
  - Managed via `devhost_cli.config.Config`
  - Values are ints (ports) or strings (e.g. `127.0.0.1:8000`, `http://host:port`, `https://host:port`)
- `~/.devhost/state.yml` — v3 **mode/proxy/tunnel/integrity** state (and a mirrored route model for v3 tooling)
  - Managed via `devhost_cli.state.StateConfig`
  - CLI keeps `state.yml` routes in sync when you `devhost add/remove`

## Key Modules

### CLI (`devhost_cli/`)
- `main.py` — `argparse` CLI (no Click/rich-click)
- `cli.py` — core commands (add/remove/list/url/open/status/etc.)
- `config.py` — `devhost.json` + domain file handling (defaults to `~/.devhost/`)
- `state.py` — `StateConfig` (proxy modes, routes mirror, tunnels, integrity hashes)
- `router_manager.py` — starts/stops the router process (uses in-repo router when available)
- `proxy.py` + `caddy_lifecycle.py` — external/system proxy integration

### Router
Devhost uses a single router implementation:

- Packaged router: `devhost_cli/router/core.py` (`--factory devhost_cli.router.core:create_app`)

The router exposes:

- `GET /health`
- `GET /metrics`
- `GET /routes`
- `GET /mappings`
- `WEBSOCKET /{full_path:path}` (wildcard WS proxy)
- `/{full_path:path}` (wildcard HTTP proxy; all common methods)

Note: there is **no** `/status` endpoint and **no** dedicated `/ws/*` route prefix — WS proxying is the wildcard websocket route.

## StateConfig API (Actual)

`StateConfig` in `devhost_cli/state.py` provides:
- `proxy_mode` (`off|gateway|system|external`), `gateway_port`, `system_domain`
- `routes` (property), `get_route(name)`, `set_route(name, upstream, domain="localhost", enabled=True, tags=None)`, `remove_route(name)`
- tunnels: `get_active_tunnel(name)`, `get_all_tunnels()`, `set_tunnel(name, tunnel_info)`, `remove_tunnel(name)`
- integrity: `record_hash(path)`, `check_all_integrity()`, `backup_file(path)`

## CLI Commands (Reality)

Core:
```bash
devhost add <name> <target>         # <port> | <host>:<port> | http(s)://<host>:<port>
devhost remove <name>
devhost list [--json]
devhost url [name]
devhost open [name]
devhost start | stop | status [--json]
devhost integrity
```

Proxy:
```bash
devhost proxy upgrade --to system|gateway
devhost proxy start|stop|status|reload
devhost proxy export [--driver caddy|nginx|traefik] [--show]
devhost proxy attach <driver> [--config-path <path>]
devhost proxy detach [--config-path <path>]
devhost proxy transfer <driver> [--config-path <path>] [--no-attach] [--no-verify] [--port 80]
```

Developer tools:
```bash
devhost dashboard                  # Textual TUI (requires: devhost[tui])
devhost tunnel start|stop|status
devhost qr [name]                  # requires: devhost[qr]
devhost oauth [name]
devhost env sync [--name <name>] [--file .env] [--dry-run]
devhost logs [-f] [-n 50] [--clear]
```

## Common Patterns (Programmatic)

### Add/update a mapping in code
```python
from devhost_cli.config import Config
from devhost_cli.state import StateConfig

cfg = Config()
routes = cfg.load()
routes["api"] = "127.0.0.1:8000"
cfg.save(routes)

# Optional: keep v3 state routes in sync for proxy/tunnel tooling
StateConfig().set_route("api", upstream="127.0.0.1:8000", domain=cfg.get_domain(), enabled=True)
```

## Testing / Linting

```bash
python -m unittest discover
python -m ruff check .
python -m ruff format --check .
```

## Dev Setup (Windows-friendly)

```bash
python -m pip install -U pip setuptools wheel
python -m pip install -e ".[dev,tui]"
```

If you see `BackendUnavailable: Cannot import 'setuptools.build_meta'`, you likely ran with `--no-build-isolation` in a venv without `setuptools`.
