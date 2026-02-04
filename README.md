# 🌐 Devhost

![CI](https://github.com/Patoruzuy/Devhost/actions/workflows/ci.yml/badge.svg)
![Release](https://img.shields.io/github/v/release/Patoruzuy/Devhost)
![PyPI](https://img.shields.io/pypi/v/devhost)
![Python](https://img.shields.io/pypi/pyversions/devhost)

**Zero-friction local development routing with subdomain support.**

Devhost eliminates "port salad" by giving your local apps memorable subdomain URLs. No more remembering `localhost:3000`, `localhost:8080`, `localhost:5173` — just use `web.localhost`, `api.localhost`, `admin.localhost`.

## ✨ Features

- **Gateway Mode** (Default): Single port `7777` for all apps — no admin required
- **System Mode**: Portless URLs on port 80/443 via Caddy
- **External Mode**: Integration with existing nginx/Traefik proxies
- **WebSocket Support**: Full bidirectional WebSocket proxying
- **Tunnel Integration**: Expose local apps via cloudflared/ngrok/localtunnel
- **TUI Dashboard**: Interactive terminal dashboard (`devhost dashboard`)
- **Cross-Platform**: Windows, macOS, Linux
- **Hot Reload**: Route changes take effect immediately

## 🚀 Quick Start

### Installation

```bash
pip install devhost
```

### Add Your First Route

```bash
# Add a route
devhost add api 8000

# List routes
devhost list

# Open in browser
devhost open api
# → Opens http://api.localhost:7777
```

### Framework Integration

```python
from flask import Flask
from devhost_cli.runner import run

app = Flask(__name__)

@app.route('/')
def index():
    return "Hello!"

if __name__ == '__main__':
    run(app, name="myapp")
    # → Accessible at http://myapp.localhost:7777
```

## 🎯 Modes

Devhost operates in three modes, each offering different trade-offs:

```
┌─────────────────────────────────────────────────────────────┐
│                      DEVHOST MODES                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Mode 1: Gateway (Default) — No admin required              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Browser → Router:7777 → App:8000                    │   │
│  │ URL: http://myapp.localhost:7777                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Mode 2: System — Portless URLs (admin required once)       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Browser → Caddy:80 → App:8000                       │   │
│  │ URL: http://myapp.localhost                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Mode 3: External — Your existing proxy                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Browser → nginx/Traefik → App:8000                  │   │
│  │ URL: http://myapp.localhost                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Mode 1: Gateway (Default)

Works immediately, no admin permissions needed:

```bash
devhost add frontend 3000    # http://frontend.localhost:7777
devhost add api 8000         # http://api.localhost:7777
devhost add admin 4200       # http://admin.localhost:7777
```

### Mode 2: System Proxy

For portless URLs (requires one-time admin setup):

```bash
devhost proxy upgrade --to system
# Now: http://myapp.localhost (no port!)
```

### Mode 3: External Proxy

Generate snippets for your existing proxy:

```bash
devhost proxy export caddy    # Generate Caddy snippet
devhost proxy export nginx    # Generate nginx config
devhost proxy attach caddy    # Attach to existing Caddyfile
```

## 📋 CLI Reference

### Core Commands

```bash
devhost add <name> <port>      # Add a route
devhost remove <name>          # Remove a route
devhost list                   # Show all routes
devhost open <name>            # Open in browser
devhost url <name>             # Print URL
devhost status                 # Show mode and health
```

### Proxy Management

```bash
devhost proxy start            # Start proxy (Gateway/System mode)
devhost proxy stop             # Stop proxy
devhost proxy status           # Show proxy status
devhost proxy upgrade --to system  # Upgrade to System mode
devhost proxy export caddy     # Export Caddy snippet
devhost proxy attach caddy     # Attach to existing config
devhost proxy detach           # Detach from config
```

### Tunnel (Expose to Internet)

```bash
devhost tunnel start [name]    # Start tunnel (auto-detects provider)
devhost tunnel stop [name]     # Stop tunnel
devhost tunnel status          # Show active tunnels
```

### Developer Features

```bash
devhost qr [name]              # QR code for mobile access
devhost oauth [name]           # Show OAuth redirect URIs
devhost env sync               # Sync .env with current URLs
devhost dashboard              # Interactive TUI dashboard
```

### Diagnostics

```bash
devhost doctor                 # Full system diagnostics
devhost validate               # Quick health check
devhost integrity check        # Verify file integrity
```

## ⚙️ Configuration

### State File

Devhost stores its configuration in `~/.devhost/state.yml`:

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
  frontend:
    upstream: "127.0.0.1:3000"
    domain: "localhost"
    enabled: true
```

### Project Config (Optional)

Create `devhost.yml` in your project for per-project settings:

```yaml
name: myapp
port: 8000
domain: localhost
auto_register: true
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DEVHOST_CONFIG` | Override config file path |
| `DEVHOST_DOMAIN` | Override base domain |
| `DEVHOST_LOG_LEVEL` | Log verbosity (DEBUG/INFO/WARNING/ERROR) |
| `DEVHOST_LOG_REQUESTS` | Enable per-request logging (1/true) |

## 🐳 Docker

```bash
docker compose up --build -d
```

The router runs on port 7777. Test with:

```bash
curl -H "Host: hello.localhost" http://127.0.0.1:7777/
```

## 🔌 WebSocket Support

Devhost automatically proxies WebSocket connections. Perfect for:

- React/Vite hot module reload
- Socket.IO applications
- Real-time dashboards
- Live collaboration tools

No configuration needed — WebSocket upgrade requests are detected and forwarded automatically.

## 🌍 Tunnel Integration

Expose your local apps to the internet:

```bash
# Auto-detect available provider
devhost tunnel start api

# Use specific provider
devhost tunnel start api --provider ngrok
devhost tunnel start api --provider cloudflared
devhost tunnel start api --provider localtunnel

# Check active tunnels
devhost tunnel status
```

Supported providers:
- **cloudflared** — Cloudflare Tunnel (free, no signup needed)
- **ngrok** — Popular tunneling service
- **localtunnel** — npm-based alternative

## 🖥️ TUI Dashboard

Launch the interactive terminal dashboard:

```bash
pip install devhost[tui]
devhost dashboard
```

Features:
- Live route status with health indicators
- Add/remove routes interactively
- Ghost port detection (find running dev servers)
- Log tailing
- Emergency reset

## 📱 Mobile Access

Generate a QR code for LAN access:

```bash
devhost qr myapp
```

## 🔧 Framework Support

### Flask

```python
from devhost_cli.frameworks.flask import run_flask
run_flask(app, name="myapp")
```

### FastAPI

```python
from devhost_cli.frameworks.fastapi import run_fastapi
run_fastapi(app, name="myapi")
```

### Django

```python
from devhost_cli.frameworks.django import run_django
run_django()
```

### ASGI Middleware

```python
from fastapi import FastAPI
from devhost_cli.middleware.asgi import DevhostMiddleware

app = FastAPI()
app.add_middleware(DevhostMiddleware)
```

### WSGI Middleware

```python
from flask import Flask
from devhost_cli.middleware.wsgi import DevhostWSGIMiddleware

app = Flask(__name__)
app.wsgi_app = DevhostWSGIMiddleware(app.wsgi_app)
```

## 🪟 Windows Notes

### PowerShell Shim

Use the PowerShell wrapper for convenience:

```powershell
.\devhost.ps1 add hello 8000
.\devhost.ps1 start
```

### Hosts File (Alternative to DNS)

If wildcard DNS isn't available:

```powershell
# Run as Administrator
devhost hosts sync   # Add entries to hosts file
devhost hosts clear  # Remove entries
```

### Port 80 Conflicts

```powershell
devhost doctor --windows       # Check what's using port 80
devhost doctor --windows --fix # Attempt to fix
```

## 🧪 Development

### Run Tests

```bash
python -m unittest discover
```

### Run Linting

```bash
python -m ruff check .
python -m ruff format --check .
```

### Run Router Locally

```bash
cd router
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 7777 --reload
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Contributing

Contributions welcome! Please read the contributing guidelines and submit PRs to the `main` branch.
