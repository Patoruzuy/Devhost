# Copilot / AI Agent Instructions for Devhost v3.0

Keep guidance concise. Focus on the three-mode architecture, state management, and common developer workflows.

## Architecture Overview

Devhost v3.0 operates in **three modes**:

1. **Gateway Mode** (default) — Router on port 7777, no admin needed
   - URL pattern: `http://myapp.localhost:7777`
   - Router: `router/app.py` (FastAPI)
   
2. **System Mode** — Caddy on port 80/443, one-time admin setup
   - URL pattern: `http://myapp.localhost` (no port)
   - Requires: `devhost proxy upgrade --to system`
   
3. **External Mode** — Integrates with existing nginx/Traefik
   - Uses config snippets: `devhost proxy export caddy|nginx`

## Key Files & Modules

### CLI Package (`devhost_cli/`)
| File | Purpose |
|------|---------|
| `main.py` | Entry point, Click command groups |
| `cli.py` | Core CLI commands (add, remove, list) |
| `config.py` | Legacy config handling (devhost.json) |
| `state.py` | v3 state management (~/.devhost/state.yml) |
| `caddy.py` | Caddy lifecycle management |
| `tunnel.py` | cloudflared/ngrok/localtunnel integration |
| `runner.py` | Framework app runner |
| `router_manager.py` | Router process management |
| `validation.py` | Target/port validation |
| `platform.py` | Platform detection |
| `windows.py` | Windows-specific helpers |

### Router (`router/`)
| File | Purpose |
|------|---------|
| `app.py` | FastAPI proxy with WebSocket support |
| `requirements.txt` | Router dependencies (httpx, websockets) |
| `Dockerfile` | Container build (port 7777) |

### Frameworks (`devhost_cli/frameworks/`)
| File | Purpose |
|------|---------|
| `flask.py` | Flask auto-run helper |
| `fastapi.py` | FastAPI auto-run helper |
| `django.py` | Django management command helper |

### Middleware (`devhost_cli/middleware/`)
| File | Purpose |
|------|---------|
| `asgi.py` | ASGI middleware for auto-registration |
| `wsgi.py` | WSGI middleware for auto-registration |

## State Management

**Primary state file**: `~/.devhost/state.yml`

```yaml
version: 3
proxy:
  mode: gateway  # gateway | system | external
  gateway:
    listen: "127.0.0.1:7777"
routes:
  api:
    upstream: "127.0.0.1:8000"
    domain: "localhost"
    enabled: true
tunnels:
  api:
    provider: cloudflared
    public_url: "https://abc123.trycloudflare.com"
    pid: 12345
```

**StateConfig class** (`state.py`):
- `get_routes()`, `set_route()`, `remove_route()`
- `get_tunnel()`, `set_tunnel()`, `remove_tunnel()`
- Auto-creates `~/.devhost/` directory

**Legacy config**: `devhost.json` (simple name→port mapping, still supported)

## Router Details

**Port**: 7777 (Gateway mode default)

**Endpoints**:
- `GET /health` — Health check
- `GET /status` — Router status + routes
- `GET /ws/{path}` — WebSocket proxy
- `GET /{path}` — HTTP proxy (all methods)

**Key functions** in `router/app.py`:
- `extract_subdomain(host, base_domain)` — Parse subdomain from Host header
- `parse_target(value)` — Normalize target (int, "host:port", or URL)
- `RouteCache.get_routes()` — Async route loading with file stat caching

**WebSocket proxy**: Bidirectional forwarding via `websockets` library

## CLI Commands

### Core
```bash
devhost add <name> <port>    # Add route
devhost remove <name>        # Remove route
devhost list                 # Show routes
devhost open <name>          # Open in browser
devhost url <name>           # Print URL
devhost status               # Show current mode
```

### Proxy Management
```bash
devhost proxy start          # Start router/Caddy
devhost proxy stop           # Stop proxy
devhost proxy status         # Show proxy status
devhost proxy upgrade --to system  # Switch to System mode
devhost proxy export caddy   # Export Caddy snippet
devhost proxy attach caddy   # Attach to existing Caddyfile
```

### Tunnels
```bash
devhost tunnel start [name] [--provider cloudflared|ngrok|localtunnel]
devhost tunnel stop [name]
devhost tunnel status
```

### Developer Tools
```bash
devhost dashboard            # TUI dashboard (requires textual)
devhost qr [name]            # QR code for LAN access
devhost oauth [name]         # OAuth redirect URIs
devhost env sync             # Sync .env with URLs
devhost doctor               # Full diagnostics
```

## Testing

```bash
# Run all tests
python -m unittest discover

# Individual test
python -m unittest tests.test_app

# Lint
python -m ruff check .
python -m ruff format --check .
```

**Test patterns**:
- Use `unittest` + `fastapi.TestClient`
- Patch `httpx.AsyncClient` for router tests
- Set `DEVHOST_CONFIG` to temp file for isolation

## Docker

```bash
docker compose up --build -d
curl -H "Host: hello.localhost" http://127.0.0.1:7777/
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DEVHOST_CONFIG` | Override config file path |
| `DEVHOST_DOMAIN` | Override base domain (default: localhost) |
| `DEVHOST_LOG_LEVEL` | DEBUG/INFO/WARNING/ERROR |
| `DEVHOST_LOG_REQUESTS` | Enable per-request logging (1/true) |

## Windows Notes

- **PowerShell shim**: `.\devhost.ps1 add hello 8000`
- **Hosts file**: `devhost hosts sync` (admin) / `devhost hosts clear`
- **Port conflicts**: `devhost doctor --windows --fix`
- **Caddy install**: Auto-detected via winget/scoop/choco

## Common Patterns

### Adding a route programmatically
```python
from devhost_cli.state import StateConfig
state = StateConfig()
state.set_route("api", {"upstream": "127.0.0.1:8000", "enabled": True})
```

### Framework auto-registration
```python
from devhost_cli.runner import run
from flask import Flask
app = Flask(__name__)
run(app, name="myapp")  # Registers + starts on random port
```

### Middleware auto-registration
```python
from fastapi import FastAPI
from devhost_cli.middleware.asgi import DevhostMiddleware
app = FastAPI()
app.add_middleware(DevhostMiddleware)
```

## Development Workflow

1. **Install editable**: `pip install -e .[dev,tui]`
2. **Start router**: `make start` or `uvicorn router.app:app --port 7777 --reload`
3. **Add routes**: `devhost add myapp 8000`
4. **Test**: `python -m unittest discover`
5. **Lint**: `python -m ruff check . && python -m ruff format --check .`
