# Devhost v3.0 Final Architecture Plan

## Summary

Mode 2 (System Proxy, owned Caddy) as primary focus; Mode 3 (External Proxy) generates snippet files with auto-import capability. Explicit `devhost proxy transfer` for Mode 2→3 migration. Rich CLI in Phase 1, Dashboard in Phase 5, WebSocket/Tunnels in Phase 6.

---

## Steps

### 1. Update ARCHITECTURE_REDESIGN.md

Replace Mode 0 default with Mode 2 focus. Document ownership model:
- `proxy.owned: true` (Mode 2) — Devhost starts/stops Caddy
- `proxy.owned: false` (Mode 3) — Devhost generates config only

Add `devhost proxy transfer` command specification for Mode 2→3 migration.

### 2. Implement Snippet Auto-Import (devhost_cli/caddy.py)

Generate snippet file at `~/.devhost/proxy/caddy/devhost.caddy`:

```caddy
# Devhost-generated routes - do not edit manually
# Regenerated on every `devhost add/remove`

myapp.localhost {
    reverse_proxy localhost:8000
}

api.localhost {
    reverse_proxy localhost:3000
}
```

**Auto-import logic:**
1. Check if user's Caddyfile exists
2. Search for existing `import` directive pointing to devhost.caddy
3. If not found, offer to append: `import ~/.devhost/proxy/caddy/devhost.caddy`
4. **Always backup** user's Caddyfile before modifying (e.g., `Caddyfile.bak`)

### 3. Add Proxy Config Discovery (devhost_cli/config.py)

Search order for external proxy configs:
```
./Caddyfile
./caddy/Caddyfile
./nginx.conf
./conf.d/*.conf
./traefik.yml
./traefik/traefik.yml
devhost.yml:external_proxy.path
```

If not found, print warning:
```
⚠️  No proxy config found.
    Specify path in devhost.yml:
      external_proxy:
        type: caddy
        path: /path/to/Caddyfile
    
    Or generate a snippet: devhost export caddy
```

### 4. Add `devhost proxy transfer` Command (devhost_cli/cli.py)

```bash
devhost proxy transfer --to external
```

**Flow:**
1. Validate external proxy is running and reachable
2. Generate snippet file with all current routes
3. Offer to auto-import into user's Caddyfile (with backup)
4. Set `proxy.owned: false` in config
5. Confirm with user before stopping owned Caddy
6. Print success message with next steps

**Error handling:**
- External proxy not found → abort with instructions
- Import failed → rollback, keep owned Caddy running
- Routes mismatch → warn user, offer manual verification

### 5. Merge Rich CLI into Phase 1

**Dependencies to add to pyproject.toml:**
```toml
dependencies = [
    "click>=8.0",
    "rich>=13.0",
    "rich-click>=1.7",
    "segno>=1.6",  # QR codes
]
```

**CLI enhancements:**
- Styled status tables for `devhost list`
- OAuth helper output on startup (redirect URIs)
- `devhost qr <name>` command for mobile QR codes
- Colored diagnostics in `devhost doctor`

### 6. Create Template File (~/.devhost/devhost.template.yml)

Installed on first run. Full reference with all options:

```yaml
# Devhost Project Configuration Template
# Copy to your project as devhost.yml and uncomment what you need
# Docs: https://github.com/user/devhost#configuration

# ─────────────────────────────────────────────────────────────
# BASIC SETTINGS
# ─────────────────────────────────────────────────────────────

# App name (becomes subdomain: myapp.localhost)
# Default: auto-detected from directory name
# name: myapp

# Port to run on (0 = auto-find free port)
# Default: 0
# port: 8000

# Base domain for subdomains
# Default: localhost
# domain: localhost

# ─────────────────────────────────────────────────────────────
# AUTO-REGISTRATION
# ─────────────────────────────────────────────────────────────

# Automatically register route on startup
# Default: true
# auto_register: true

# Automatically configure Caddy (Mode 2 only)
# Default: true
# auto_caddy: true

# ─────────────────────────────────────────────────────────────
# OAUTH HELPER
# ─────────────────────────────────────────────────────────────

# oauth:
#   # Common OAuth callback paths to print on startup
#   callback_paths:
#     - /callback
#     - /oauth/callback
#     - /auth/callback
#     - /api/auth/callback
#
#   # OAuth providers to detect and show URIs for
#   providers:
#     - google
#     - github
#     - facebook

# ─────────────────────────────────────────────────────────────
# ENVIRONMENT SYNC
# ─────────────────────────────────────────────────────────────

# env_sync:
#   # Keep .env APP_URL in sync with subdomain
#   enabled: true
#   
#   # Environment file to update
#   file: .env
#   
#   # Variables to sync (key: template with {url}, {domain}, {name})
#   variables:
#     APP_URL: "{url}"
#     ALLOWED_HOSTS: "{domain}"

# ─────────────────────────────────────────────────────────────
# EXTERNAL PROXY (Mode 3)
# ─────────────────────────────────────────────────────────────

# external_proxy:
#   # Proxy type: caddy, nginx, traefik
#   type: caddy
#   
#   # Path to proxy config file (if not auto-discovered)
#   path: /etc/caddy/Caddyfile
#   
#   # Whether to auto-import devhost snippet
#   auto_import: true
#   
#   # Reload command after config changes
#   reload_command: "systemctl reload caddy"

# ─────────────────────────────────────────────────────────────
# MOBILE / LAN ACCESS
# ─────────────────────────────────────────────────────────────

# mobile:
#   # Show QR code on startup for LAN access
#   show_qr: true
#   
#   # Bind to LAN IP instead of localhost
#   lan_bind: false

# ─────────────────────────────────────────────────────────────
# TUNNEL INTEGRATION (Phase 6)
# ─────────────────────────────────────────────────────────────

# tunnel:
#   # Tunnel provider: cloudflared, ngrok, localtunnel
#   provider: cloudflared
#   
#   # Auto-start tunnel on app startup
#   auto_start: false
#   
#   # Custom subdomain (if supported by provider)
#   subdomain: myapp
```

**Installation:**
- `devhost init` → creates minimal devhost.yml
- `devhost init --from-template` → copies full template to project

---

## Implementation Phases (Revised)

| Phase | Weeks | Focus | Key Deliverables |
|-------|-------|-------|------------------|
| **1** | 1-2 | Config consolidation + Rich CLI + fix CI | Single config source, styled output, passing tests |
| **2** | 3-4 | Mode 2 polish | OAuth helper, QR codes, env sync |
| **3** | 5-6 | Mode 3: External proxy | Snippet generation, auto-import, `proxy transfer` |
| **4** | 7-8 | Caddy lifecycle + Windows | Ownership model, port 80 conflicts, better detection |
| **5** | 9-10 | Dashboard (Textual TUI) | Live routes, log tailing, interactive mode |
| **6** | 11-12 | WebSocket + Tunnels | WebSocket proxying, cloudflared/ngrok integration |

---

## Ownership Model

### Mode 2: System Proxy (Owned)

```
proxy:
  mode: system
  owned: true
  caddy_pid: 12345
```

**Behavior:**
- Devhost starts Caddy on `devhost caddy start`
- Devhost stops Caddy on exit **only if no other routes active**
- Devhost regenerates Caddyfile on every route change
- Devhost owns the process lifecycle

**Caddy lifecycle rules:**
```python
def should_stop_caddy():
    routes = load_routes()
    if len(routes) == 0:
        return True  # No routes, stop Caddy
    if all(route.status == "stopped" for route in routes):
        return True  # All apps stopped
    return False  # Keep running
```

### Mode 3: External Proxy (Not Owned)

```
proxy:
  mode: external
  owned: false
  type: caddy
  config_path: /etc/caddy/Caddyfile
  snippet_path: ~/.devhost/proxy/caddy/devhost.caddy
```

**Behavior:**
- Devhost **never** starts/stops the proxy
- Devhost generates snippet file only
- User manages proxy lifecycle
- Devhost may trigger reload command if configured

**Never-touch rules:**
- Never modify user's main Caddyfile (except import line with permission)
- Never kill external proxy process
- Never assume proxy state

---

## Snippet Generation

### Caddy (`~/.devhost/proxy/caddy/devhost.caddy`)

```caddy
# Auto-generated by Devhost - do not edit
# Last updated: 2026-02-03T10:30:00Z
# Routes: 3 active

myapp.localhost {
    reverse_proxy localhost:8000
}

api.localhost {
    reverse_proxy localhost:3000
}

dashboard.localhost {
    reverse_proxy localhost:5173
}
```

### nginx (`~/.devhost/proxy/nginx/devhost.conf`)

```nginx
# Auto-generated by Devhost - do not edit
# Include in nginx.conf: include ~/.devhost/proxy/nginx/devhost.conf;

server {
    listen 80;
    server_name myapp.localhost;
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 80;
    server_name api.localhost;
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Traefik (`~/.devhost/proxy/traefik/devhost.yml`)

```yaml
# Auto-generated by Devhost - do not edit
# Add to traefik.yml: providers.file.filename: ~/.devhost/proxy/traefik/devhost.yml

http:
  routers:
    myapp:
      rule: "Host(`myapp.localhost`)"
      service: myapp-service
    api:
      rule: "Host(`api.localhost`)"
      service: api-service

  services:
    myapp-service:
      loadBalancer:
        servers:
          - url: "http://localhost:8000"
    api-service:
      loadBalancer:
        servers:
          - url: "http://localhost:3000"
```

---

## Auto-Import Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    devhost export caddy                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Generate ~/.devhost/proxy/caddy/devhost.caddy           │
│                         │                                   │
│                         ▼                                   │
│  2. Find user's Caddyfile (discovery order)                 │
│     ├── ./Caddyfile                                         │
│     ├── ./caddy/Caddyfile                                   │
│     ├── ~/.config/caddy/Caddyfile                           │
│     └── devhost.yml:external_proxy.path                     │
│                         │                                   │
│                         ▼                                   │
│  3. Check if import exists                                  │
│     └── grep "import.*devhost.caddy"                        │
│                         │                                   │
│            ┌────────────┴────────────┐                      │
│            ▼                         ▼                      │
│     Already imported            Not imported                │
│     └── Done ✓                  └── Prompt user             │
│                                      │                      │
│                         ┌────────────┴────────────┐         │
│                         ▼                         ▼         │
│                     User: Yes                 User: No      │
│                     └── Backup Caddyfile      └── Print     │
│                         └── Append import         manual    │
│                             └── Reload Caddy      steps     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## CLI Commands (Revised)

```bash
# Core (all modes)
devhost add <name> <port>        # Register route
devhost remove <name>            # Remove route
devhost list                     # Show routes (Rich table)
devhost open <name>              # Open in browser
devhost url <name>               # Print URL

# Developer Features (Phase 2)
devhost qr [name]                # QR code for mobile access
devhost oauth [name]             # Print OAuth redirect URIs
devhost env sync                 # Sync .env with current URL

# Mode 2: System Proxy
devhost caddy start              # Start owned Caddy (admin)
devhost caddy stop               # Stop owned Caddy
devhost caddy restart            # Restart Caddy
devhost caddy status             # Show Caddy status

# Mode 3: External Proxy
devhost export caddy|nginx|traefik  # Generate snippet
devhost proxy transfer --to external  # Migrate Mode 2→3

# Diagnostics
devhost doctor                   # Full system check
devhost validate                 # Quick health check
devhost status                   # Current mode + routes

# Setup
devhost init                     # Create minimal devhost.yml
devhost init --from-template     # Create full devhost.yml
devhost install --system         # Setup Mode 2 (admin)

# Future (Phase 5-6)
devhost dashboard                # Interactive TUI
devhost tunnel start             # Start tunnel
```

---

## Developer Features Detail

### OAuth Helper

On startup, detect OAuth libraries and print redirect URIs:

```
🚀 Starting myapp...
   Framework: Flask
   Port: 8000

🌐 Access at: http://myapp.localhost

🔐 OAuth Redirect URIs:
   http://myapp.localhost/callback
   http://myapp.localhost/oauth/callback
   http://myapp.localhost/auth/google/callback

   Add these to your OAuth provider's allowed redirect URIs.
```

**Detection:**
- Flask: `flask-dance`, `authlib`, `flask-oauthlib`
- Django: `social-auth-app-django`, `django-allauth`
- FastAPI: `authlib`, `fastapi-users`

### QR Code (Mobile Access)

```bash
$ devhost qr myapp

█▀▀▀▀▀█ ▄▄▄▄▄ █▀▀▀▀▀█
█ ███ █ █▄▄▄█ █ ███ █
█ ▀▀▀ █ ▀▀▀▀▀ █ ▀▀▀ █
▀▀▀▀▀▀▀ █ ▀ █ ▀▀▀▀▀▀▀
▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀

📱 Scan to access: http://192.168.1.100:8000
   (Make sure your phone is on the same network)
```

### Env Sync

```bash
$ devhost env sync

✓ Updated .env:
   APP_URL=http://myapp.localhost
   ALLOWED_HOSTS=myapp.localhost
```

---

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Default mode | Mode 2 (System Proxy) | Portless URLs are the core value prop |
| Snippet approach | Separate file + import | Never modify user's main config |
| Auto-import | Offer with backup | Safe, reversible, user-controlled |
| Mode migration | Explicit `proxy transfer` | Verify external proxy before switching |
| Caddy lifecycle | Kill if no routes | Prevent orphaned processes |
| External proxy lifecycle | Never touch | Not our process to manage |
| Rich CLI | Phase 1 (merged) | Better UX from day one |
| Dashboard | Phase 5 (optional) | Core features first |
| WebSocket | Phase 6 | After stability |
| Tunnel | Phase 6 | After stability |

---

## Files to Modify

| File | Changes |
|------|---------|
| `pyproject.toml` | Add rich, rich-click, segno dependencies |
| `devhost_cli/cli.py` | Rich output, new commands (qr, oauth, env, proxy transfer) |
| `devhost_cli/caddy.py` | Snippet generation, auto-import logic |
| `devhost_cli/config.py` | Ownership model, proxy mode, discovery |
| `devhost_cli/utils.py` | LAN IP detection, QR generation |
| `ARCHITECTURE_REDESIGN.md` | Update with Mode 2 focus, ownership model |

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Time to portless URL | < 2 min (one-time setup) |
| CLI commands for daily use | 3-4 (`add`, `list`, `open`) |
| Config files to understand | 1 (`devhost.yml`) |
| External proxy setup time | < 5 min |
| QR to mobile access | < 10 sec |
