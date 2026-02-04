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

**Developer Benefits** (concrete friction removers):

1. **OAuth/OIDC Redirect URIs**
   - Problem: OAuth providers require exact URLs
   - Solution: Use stable subdomain URLs instead of changing ports
   - Example: `http://auth.localhost:7777/callback` always works

2. **Cookie Domain Isolation**
   - Problem: Cookies on `localhost:3000` leak to `localhost:8080`
   - Solution: `web.localhost` and `api.localhost` are separate domains
   - Benefit: No cross-app auth bugs

3. **SameSite Cookie Policy**
   - Problem: Modern browsers block third-party cookies on `localhost:PORT`
   - Solution: Subdomains enable proper SameSite testing
   - Benefit: Match production cookie behavior

4. **CORS Testing**
   - Problem: CORS doesn't trigger on same `localhost:PORT`
   - Solution: Different subdomains = real CORS scenarios
   - Benefit: Catch CORS issues before production

5. **Service Worker Scope**
   - Problem: Service workers scope to `localhost:PORT`
   - Solution: Subdomains provide clean scope isolation
   - Benefit: Test PWA features properly

6. **Mobile Device Testing**
   - Problem: Mobile can't hit `localhost:PORT`
   - Solution: Single gateway port + LAN access = easy testing
   - Benefit: Test on real devices without complex setup

7. **Multi-Tenant Development**
   - Problem: Testing tenant isolation with ports is messy
   - Solution: `tenant1.localhost:7777`, `tenant2.localhost:7777`
   - Benefit: Realistic multi-tenant scenarios

8. **Microservices Architecture**
   - Problem: Remembering 10+ ports for different services
   - Solution: Memorable names: `api.localhost`, `auth.localhost`, `payments.localhost`
   - Benefit: Single port to remember (7777), names are semantic

9. **TLS/HTTPS Matching**
   - Problem: Can't test HTTPS redirects with bare `localhost:PORT`
   - Solution: Subdomains work with local TLS certificates
   - Benefit: Match production HTTPS behavior

10. **Browser DevTools**
    - Problem: Network tab full of `localhost:XXXX` requests
    - Solution: Filter by subdomain for cleaner debugging
    - Benefit: Faster issue diagnosis, less cognitive load

### Mode 2: System Proxy

For portless URLs (requires one-time admin setup):

```bash
devhost proxy upgrade --to system
# Now: http://myapp.localhost (no port!)
```

**Developer Benefits** (production parity):

1. **Production URL Matching**
   - Problem: Production uses `app.example.com`, dev uses `localhost:3000`
   - Solution: `app.localhost` mirrors production URL structure
   - Benefit: Catch URL-dependent bugs early

2. **Hardcoded URL Detection**
   - Problem: Code with hardcoded ports breaks in production
   - Solution: Portless URLs expose hardcoded dependencies
   - Benefit: Force proper configuration management

3. **Browser Extension Testing**
   - Problem: Extensions often reject `localhost:PORT` URLs
   - Solution: Standard ports (80/443) match extension expectations
   - Benefit: Test browser extensions realistically

4. **CDN/Asset Simulation**
   - Problem: Production serves assets from CDN on port 443
   - Solution: Local HTTPS on port 443 matches production behavior
   - Benefit: Catch mixed-content warnings

5. **Third-Party Integration**
   - Problem: Payment/auth providers whitelist domains without ports
   - Solution: `payments.localhost` (no port) matches their requirements
   - Benefit: Test real integrations locally

6. **Mobile App API Testing**
   - Problem: Mobile apps expect standard ports
   - Solution: Configure app to hit `api.localhost` (port 80/443)
   - Benefit: No app reconfiguration between dev/prod

7. **Demo/Presentation Mode**
   - Problem: Showing `:7777` in URLs looks unprofessional
   - Solution: Clean URLs look production-ready
   - Benefit: Better client demos

8. **Subdomain Cookie Wildcards**
   - Problem: Production sets cookies on `*.example.com`
   - Solution: Test with `*.localhost` on standard ports
   - Benefit: Match production cookie behavior exactly

9. **SSL/TLS Certificate Testing**
   - Problem: Self-signed certs often fail on non-standard ports
   - Solution: Port 443 matches production certificate expectations
   - Benefit: Realistic HTTPS testing

10. **Developer Muscle Memory**
    - Problem: Constantly typing `:7777` is cognitive overhead
    - Solution: Just type the domain, browser defaults to port 80
    - Benefit: Faster workflow, less mental friction

### Mode 3: External Proxy

Generate snippets for your existing proxy:

```bash
devhost proxy export caddy    # Generate Caddy snippet
devhost proxy export nginx    # Generate nginx config
devhost proxy attach caddy    # Attach to existing Caddyfile
```

**Developer Benefits** (infrastructure integration):

1. **Brownfield Integration**
   - Problem: You already have nginx/Traefik managing 50+ routes
   - Solution: Generate snippets, don't replace your entire setup
   - Benefit: Adopt Devhost incrementally without migration risk

2. **Team Configuration Consistency**
   - Problem: Each developer configures their proxy differently
   - Solution: Export canonical snippets from Devhost state
   - Benefit: Team-wide routing consistency

3. **Custom Proxy Features**
   - Problem: Need advanced features (rate limiting, auth middleware)
   - Solution: Devhost generates base config, you add custom logic
   - Benefit: Leverage existing proxy expertise

4. **Multi-Environment Parity**
   - Problem: Dev proxy doesn't match staging/production setup
   - Solution: Use same proxy (nginx/Traefik) across all environments
   - Benefit: "Works on my machine" bugs eliminated

5. **Configuration Drift Detection**
   - Problem: Manual edits break Devhost-generated routes
   - Solution: Integrity checking warns when snippets diverge
   - Benefit: Know exactly when manual changes conflict

6. **Zero Trust Required**
   - Problem: Worried Devhost will break your proxy setup?
   - Solution: Export-only mode never touches your files
   - Benefit: Review generated config before applying

7. **Emergency Escape Hatch**
   - Problem: Devhost breaks, need to revert immediately
   - Solution: Detach removes only marked sections, preserves rest
   - Benefit: Safe experimentation with quick rollback

8. **Legacy System Compatibility**
   - Problem: Corporate proxy with strict config requirements
   - Solution: Generate compliant snippets matching your standards
   - Benefit: Works within existing constraints

9. **Documentation as Code**
   - Problem: Proxy config comments get stale or lost
   - Solution: Devhost state is canonical, generates fresh snippets
   - Benefit: Config always matches documented routes

10. **Gradual Adoption Path**
    - Problem: Can't commit to new tools without trial period
    - Solution: Export → Manual review → Attach → Verify → Adopt
    - Benefit: Low-risk evaluation with clear rollback steps

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
