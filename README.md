# 🌐 Devhost

![CI](https://github.com/Patoruzuy/Devhost/actions/workflows/ci.yml/badge.svg)
[![Security Scan](https://github.com/Patoruzuy/Devhost/actions/workflows/security-scan.yml/badge.svg?event=pull_request)](https://github.com/Patoruzuy/Devhost/actions/workflows/security-scan.yml)
![Release](https://img.shields.io/github/v/release/Patoruzuy/Devhost)
[![PyPI](https://github.com/Patoruzuy/Devhost/actions/workflows/publish.yml/badge.svg)](https://github.com/Patoruzuy/Devhost/actions/workflows/publish.yml)
![Python](https://img.shields.io/pypi/pyversions/devhost)

**Stop memorizing ports. Start using real domains.**

```bash
# Before: The Port Juggling Hell 😫
http://localhost:3000   # Which app is this again?
http://localhost:8080   # Frontend or backend?
http://localhost:5173   # Wait, did I change the port?

# After: Devhost Makes It Obvious 🎯

# Gateway Mode (works instantly, no setup)
http://web.localhost:7777
http://api.localhost:7777
http://admin.localhost:7777

# System/External Mode (production-like URLs)
http://web.localhost
http://api.localhost
http://admin.localhost
```

**What is Devhost?** A local development router that gives every project its own subdomain. One command, zero config, works instantly on any OS.

## Why You Need This

**The Problem:** Working on modern apps means running 5+ services. You're constantly:
- 🤯 Forgetting which port runs what (`Was it 3000 or 3001?`)
- 🔒 Breaking OAuth redirects when you restart your server on a different port
- 🍪 Fighting cookie/CORS issues because everything's on `localhost`
- 📱 Struggling to test on your phone (`http://192.168.1.whatever:8080`?)
- 🔗 Sharing broken links with your team (`localhost` only works for you)

**The Solution:** Devhost routes all your apps through meaningful subdomains on a single port. No admin rights needed, works in 60 seconds.

## 🚀 Get Started in 60 Seconds

```bash
# 1. Install (one command)
pip install "devhost[tui]"

# 2. Start routing
devhost start

# 3. Register your app
devhost add web 3000

# 4. Open in browser
devhost open web
# → Opens http://web.localhost:7777
```

**That's it.** Your React/Vue/Next.js app now has a real subdomain. Add more apps the same way.

---

## ✨ What Makes Devhost Different

### 🎯 **Works Immediately** (Gateway Mode - Default)
- No admin rights required
- No Docker, no containers, no VMs
- Pure Python, runs anywhere
- One port (`:7777`) routes everything

### 🔒 **Production-Ready Features**
- **WebSocket Support**: Hot reload, Socket.IO, real-time apps work out of the box
- **HTTPS/TLS**: Full certificate management (optional System Mode)
- **Security Hardened**: SSRF protection, input validation, secure defaults
- **Tunnel Integration**: Expose to internet with cloudflared/ngrok (one command)

### 🛠️ **Developer Experience**
- **Interactive Dashboard**: Feature-rich TUI with keyboard shortcuts, draft mode, and contextual help (`devhost dashboard`)
  - Press `F1` for complete keyboard reference
  - Visual progress bars and status indicators
  - Safety confirmations and error boundaries
  - Accessible design (screen reader friendly)
- **OAuth Testing**: Stable redirect URLs that don't break when you restart
- **Mobile Testing**: Access from your phone (`http://api.localhost:7777`)
- **Framework Integration**: Drop-in support for Flask, FastAPI, Django
- **Team Sharing**: Export routes as nginx/Caddy configs (External Mode)

### 🚀 **Three Modes, One Tool**

```
┌─────────────────────────────────────────────────┐
│  Gateway Mode (Default)                         │
│  ✓ Works instantly, no setup                    │
│  ✓ Port 7777 routes all apps                    │
│  ✓ http://app.localhost:7777                    │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  System Mode (Optional)                         │
│  ✓ Portless URLs (ports 80/443)                 │
│  ✓ Managed Caddy with auto-certs                │
│  ✓ http://app.localhost (production-like)       │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  External Mode (Advanced)                       │
│  ✓ Integrate with existing nginx/Traefik        │
│  ✓ Generate config snippets                     │
│  ✓ Team consistency without lock-in             │
└─────────────────────────────────────────────────┘
```

---

## 🎬 Real-World Use Cases

### 🏗️ Microservices Development
```bash
devhost add frontend 3000
devhost add api 8000
devhost add auth 4000
devhost add db-admin 5432

# Access everything with meaningful names
http://frontend.localhost:7777
http://api.localhost:7777
http://auth.localhost:7777
http://db-admin.localhost:7777
```

### 🔐 OAuth/OIDC Testing
```bash
# Your OAuth redirect URL stays stable
# (No more "redirect_uri mismatch" errors when you restart!)

Redirect URI: http://auth.localhost:7777/callback
→ Works every time, even after restarts
```

### 📱 Mobile App Development
```bash
devhost tunnel start api
# → Exposes http://api.localhost:7777 as https://random-url.trycloudflare.com
# → Test your mobile app against your local backend
```

### 👥 Team Development
```bash
# Export your setup for the team
devhost proxy export --driver nginx > team-nginx.conf

# Everyone uses the same subdomain structure
# → No more "works on my machine" URL issues
```

---

## 📖 Documentation

- **[Why Devhost?](https://github.com/Patoruzuy/Devhost/blob/main/docs/why.md)** — Detailed benefits and comparisons
- **[Installation](https://github.com/Patoruzuy/Devhost/blob/main/docs/installation.md)** — OS-specific setup guides  
- **[Getting Started](https://github.com/Patoruzuy/Devhost/blob/main/docs/getting-started.md)** — Comprehensive tutorial
- **[Proxy Modes](https://github.com/Patoruzuy/Devhost/blob/main/docs/modes.md)** — Gateway vs System vs External
- **[CLI Reference](https://github.com/Patoruzuy/Devhost/blob/main/docs/cli.md)** — All commands and options
- **[Security Guide](https://github.com/Patoruzuy/Devhost/blob/main/docs/security-configuration.md)** — Security features and best practices
- **[Performance Tuning](https://github.com/Patoruzuy/Devhost/blob/main/docs/performance.md)** — Optimization and monitoring
- **[Architecture](https://github.com/Patoruzuy/Devhost/blob/main/docs/architecture.md)** — How it works internally

---

## 🔒 Built for Safety

Devhost is designed for **local development only** with security baked in:

- ✅ **Localhost-only binding** — Never exposed to your network by default
- ✅ **SSRF protection** — Blocks cloud metadata endpoints and private networks  
- ✅ **Input validation** — All routes and hostnames validated before use
- ✅ **No privilege required** — Gateway mode runs as a regular user
- ✅ **Audit logging** — Track all configuration changes

Need to proxy to your LAN? Set `DEVHOST_ALLOW_PRIVATE_NETWORKS=1` explicitly.

📖 **Full security documentation**: [Security Guide](https://github.com/Patoruzuy/Devhost/blob/main/docs/security-configuration.md)

---

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
- ❌ **No hidden state**: All configuration is in `~/.devhost/state.yml` and `~/.devhost/devhost.json` — no mysterious database
- ❌ **No app process management**: Devhost routes traffic; it doesn’t own your app lifecycle (use your normal `npm run dev`, `uvicorn`, etc., or the optional `devhost_cli.runner.run()` helper)
- ❌ **No production deployment**: Strictly for local development — never use in production environments

### Clear Ownership Boundaries

- **Devhost owns**: Router process, Caddy (in System mode), `~/.devhost/state.yml`, `~/.devhost/devhost.json`, generated snippets
- **You own**: Your apps, existing proxy configs, system DNS settings, hosts file entries
- **Opt-in only**: Features like tunnel exposure, TUI dashboard, and External mode require explicit commands

### One Mental Model Per Mode

- **Gateway**: "Single port for everything, works immediately"
- **System**: "Portless URLs with managed Caddy"
- **External**: "Generate snippets for my existing setup"

No ambiguity. Each mode has a clear, concrete outcome.

---

## 🔒 Security

Devhost is built for **local development only** with security hardened by default: SSRF protection, input validation, localhost-only binding, and no privilege escalation.

📖 **Full security details**: [Security Guide](https://github.com/Patoruzuy/Devhost/blob/main/docs/security-configuration.md)

## 🚀 Quick Start

### Installation

```bash
# Core installation
pip install devhost

# With optional dependencies
pip install devhost[flask]      # Flask integration helpers
pip install devhost[fastapi]    # FastAPI integration helpers
pip install devhost[django]     # Django integration
pip install devhost[tui]        # Interactive dashboard (optional, uninstall anytime)
pip install devhost[qr]         # QR code generation
pip install devhost[dev]        # Tests + linting (contributors)

# Install everything
pip install devhost[all]
```

> **Note**: The TUI dashboard is completely optional. Install with `pip install devhost[tui]` when you need it, uninstall with `pip uninstall textual psutil` when you don't. The CLI works independently.

### Add Your First Route

```bash
# Start the Gateway router (Mode 1)
devhost start

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
    # (Auto-registers the route and starts the Gateway router if needed)
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

**[See all 10 benefits →](https://github.com/Patoruzuy/Devhost/blob/main/BENEFITS.md#mode-1-gateway-default)**

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

**[See all 11 benefits →](https://github.com/Patoruzuy/Devhost/blob/main/BENEFITS.md#mode-2-system-portless-urls)**

### Mode 3: External Proxy

Generate snippets for your existing proxy:

```bash
devhost proxy export --driver caddy   # Generate Caddy snippet
devhost proxy export --driver nginx   # Generate nginx config
devhost proxy attach caddy    # Attach to existing Caddyfile
```

**Key Benefits** (brownfield integration):

1. **Incremental Adoption** — Already have nginx/Traefik managing 50+ routes? Generate snippets, don't replace your entire setup. Zero migration risk.

2. **Configuration Drift Detection** — Manual edits break Devhost-generated routes? Integrity checking warns when snippets diverge, so you know exactly when manual changes conflict.

3. **Zero Trust Required** — Worried Devhost will break your proxy? Export-only mode never touches your files. Review generated config before applying.

4. **Emergency Escape Hatch** — Devhost breaks, need to revert immediately? Detach removes only marked sections, preserves the rest. Safe experimentation with quick rollback.

**[See all 10 benefits →](https://github.com/Patoruzuy/Devhost/blob/main/BENEFITS.md#mode-3-external-infrastructure-integration)**

## 📋 Core Commands

```bash
# Essential commands
devhost start                      # Start router
devhost add <name> <port>           # Add route
devhost list                        # Show all routes
devhost open <name>                 # Open in browser

# Mode upgrades
devhost proxy upgrade --to system   # Portless URLs
devhost proxy export --driver nginx # Generate config

# Advanced features
devhost tunnel start [name]         # Expose to internet
devhost dashboard                   # Visual TUI
```

📖 **Full CLI reference**: [docs/cli.md](https://github.com/Patoruzuy/Devhost/blob/main/docs/cli.md)

## ⚙️ Configuration

Devhost stores routes in `~/.devhost/devhost.json` and state in `~/.devhost/state.yml`.

**Quick tips:**
- Use `DEVHOST_CONFIG` to point to a project-local config file
- Use `DEVHOST_DOMAIN=home` for custom domains (`http://api.home:7777`)
- Use `DEVHOST_LOG_LEVEL=DEBUG` for troubleshooting

📖 **Full configuration guide**: [docs/configuration.md](https://github.com/Patoruzuy/Devhost/blob/main/docs/configuration.md)

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

> Tunnel providers are external CLIs. Install at least one (`cloudflared`, `ngrok`, or `lt`) and Devhost will use it.

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

## 🔧 Framework Integration

```python
# All frameworks (auto-detected)
from devhost_cli.runner import run
run(app, name="myapp")

# Works with Flask, FastAPI, Django, and more
# The runner automatically detects your framework and runs it appropriately
```

📖 **Middleware and advanced integration**: See [examples/](https://github.com/Patoruzuy/Devhost/tree/main/examples)

---

## 🪟 Windows | 🐳 Docker | 🧪 Development

- **Windows users**: See [Windows setup guide](https://github.com/Patoruzuy/Devhost/blob/main/docs/installation.md#windows) for PowerShell wrapper and port 80 troubleshooting
- **Docker**: Run `docker compose up --build -d` — router available on port 7777
- **Contributors**: See [docs/architecture.md](https://github.com/Patoruzuy/Devhost/blob/main/docs/architecture.md) for development setup

---

## 📄 License

MIT License - see [LICENSE](https://github.com/Patoruzuy/Devhost/blob/main/LICENSE) for details.

## 🙏 Contributing

Contributions welcome! Please read the contributing guidelines and submit PRs to the `main` branch.
