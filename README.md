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

## 🧭 Product Principles (Non-Negotiables)

### What Devhost Does

**Gateway Mode** (Default):
- ✅ Routes all your local apps through a single port (7777)
- ✅ Provides memorable subdomain URLs without admin permissions
- ✅ Proxies HTTP and WebSocket traffic bidirectionally
- ✅ Works immediately on all platforms (Windows, macOS, Linux)

**System Mode** (Optional):
- ✅ Manages Caddy lifecycle for portless URLs (80/443)
- ✅ Generates Caddyfile from your routes automatically
- ✅ Requires one-time admin setup, then runs seamlessly

**External Mode** (Advanced):
- ✅ Generates config snippets for your existing proxy (nginx/Traefik)
- ✅ Detects config drift and offers emergency reset
- ✅ Integrates with your infrastructure, doesn't replace it

### What Devhost Does NOT Do

- ❌ **Never surprise-edits user files**: Any edit to user-owned files (like existing Caddyfiles) must be explicit, backed up, and reversible
- ❌ **No automatic LAN exposure**: Defaults to loopback (127.0.0.1) to prevent accidental network exposure
- ❌ **No hidden state**: All configuration is in `~/.devhost/state.yml` and `devhost.json` — no mysterious database
- ❌ **No process management beyond router/Caddy**: Won't start/stop your apps automatically (use `devhost run` explicitly)
- ❌ **No production deployment**: Strictly for local development — never use in production environments

### Clear Ownership Boundaries

- **Devhost owns**: Router process, Caddy (in System mode), `~/.devhost/state.yml`, generated snippets
- **You own**: Your apps, existing proxy configs, system DNS settings, hosts file entries
- **Opt-in only**: Features like tunnel exposure, TUI dashboard, and External mode require explicit commands

### One Mental Model Per Mode

- **Gateway**: "Single port for everything, works immediately"
- **System**: "Portless URLs with managed Caddy"
- **External**: "Generate snippets for my existing setup"

No ambiguity. Each mode has a clear, concrete outcome.

## 🚀 Quick Start

### Installation

```bash
# Core installation
pip install devhost

# With optional dependencies
pip install devhost[flask]      # Flask integration
pip install devhost[fastapi]    # FastAPI integration  
pip install devhost[django]     # Django integration
pip install devhost[tui]        # Interactive dashboard (optional, uninstall anytime)
pip install devhost[qr]         # QR code generation
pip install devhost[tunnel]     # Tunnel providers (cloudflared, ngrok, localtunnel)

# Install everything
pip install devhost[all]
```

> **Note**: The TUI dashboard is completely optional. Install with `pip install devhost[tui]` when you need it, uninstall with `pip uninstall textual psutil` when you don't. The CLI works independently.

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

**Key Benefits** (why use a gateway?):

1. **Microservices Made Easy** — Remembering 10+ ports is cognitive overhead. Use `api.localhost`, `auth.localhost`, `payments.localhost` — single port (7777), semantic names.

2. **OAuth/OIDC That Just Works** — OAuth providers need exact URLs. `http://auth.localhost:7777/callback` never changes, even when your app port does.

3. **Cookie Domain Isolation** — Cookies on `localhost:3000` leak to `localhost:8080`, causing weird auth bugs. `web.localhost` and `api.localhost` are separate domains.

4. **Real CORS Testing** — CORS doesn't trigger on same `localhost:PORT`. Different subdomains = catch CORS issues before production.

[See all 10 benefits](BENEFITS.md#mode-1-gateway-default) including SameSite cookies, Service Workers, mobile testing, TLS/HTTPS matching, and more.

### Mode 2: System Proxy

For portless URLs (requires one-time admin setup):

```bash
devhost proxy upgrade --to system
# Now: http://myapp.localhost (no port!)
```

**Key Benefits** (production parity):

1. **Production URL Matching** — Production uses `app.example.com`, dev uses `localhost:3000`? Use `app.localhost` to mirror production URL structure and catch bugs early.

2. **IoT & Home Lab Access** — Raspberry Pi at `192.168.1.50:8080`, NAS at `192.168.1.100:5000`? Use `http://homelab.raspberry` or `http://nas.home` — forget IPs and ports across your local network. (Use any domain you want, not just `.localhost`!)

3. **Third-Party Integrations** — Payment/auth providers whitelist domains without ports. `payments.localhost` (no port) matches their requirements for realistic local testing.

4. **Professional Demos** — Showing `:7777` in URLs looks unprofessional. Clean portless URLs look production-ready for client presentations.

[See all 11 benefits](BENEFITS.md#mode-2-system-portless-urls) including hardcoded URL detection, browser extensions, mobile app testing, SSL/TLS certificates, and more.

### Mode 3: External Proxy

Generate snippets for your existing proxy:

```bash
devhost proxy export caddy    # Generate Caddy snippet
devhost proxy export nginx    # Generate nginx config
devhost proxy attach caddy    # Attach to existing Caddyfile
```

**Key Benefits** (brownfield integration):

1. **Incremental Adoption** — Already have nginx/Traefik managing 50+ routes? Generate snippets, don't replace your entire setup. Zero migration risk.

2. **Configuration Drift Detection** — Manual edits break Devhost-generated routes? Integrity checking warns when snippets diverge, so you know exactly when manual changes conflict.

3. **Zero Trust Required** — Worried Devhost will break your proxy? Export-only mode never touches your files. Review generated config before applying.

4. **Emergency Escape Hatch** — Devhost breaks, need to revert immediately? Detach removes only marked sections, preserves the rest. Safe experimentation with quick rollback.

[See all 10 benefits](BENEFITS.md#mode-3-external-infrastructure-integration) including team consistency, custom features, multi-environment parity, legacy compatibility, and more.

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
| `DEVHOST_DOMAIN` | Override base domain (default: `localhost`). Examples: `home`, `lab`, `dev` |
| `DEVHOST_LOG_LEVEL` | Log verbosity (DEBUG/INFO/WARNING/ERROR) |
| `DEVHOST_LOG_REQUESTS` | Enable per-request logging (1/true) |

**Custom Domains**: Set `DEVHOST_DOMAIN=home` to use `http://api.home:7777` instead of `http://api.localhost:7777`. Perfect for IoT/home lab setups!

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

## 🖥️ TUI Dashboard (Optional)

**The dashboard is completely optional** — install only when you need a visual interface. The CLI works independently.

Launch the interactive terminal dashboard:

```bash
# Install (only when needed)
pip install devhost[tui]

# Run
devhost dashboard

# Uninstall (anytime)
pip uninstall textual psutil
```

Features:
- Live route status with health indicators
- Add/remove routes interactively
- Ghost port detection (find running dev servers)
- Integrity drift detection
- Visual flow diagrams
- Log tailing
- Emergency reset (safety boundaries enforced)
- Profile switching for multi-context workflows

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
