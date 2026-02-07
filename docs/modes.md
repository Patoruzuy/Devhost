# Proxy Modes

Devhost supports three active proxy modes and an "Off" state. The active mode is stored globally in `~/.devhost/state.yml`.

## Mode 1: Gateway (Default)

**Goal**: Immediate value with zero system configuration.

- **How it works**: Devhost starts a lightweight FastAPI-based router on port `7777`.
- **URL Pattern**: `http://<name>.<domain>:7777` (e.g., `http://api.localhost:7777`).
- **Permissions**: No administrator or root privileges required.
- **Binding**: Localhost-only by default (`127.0.0.1`).
- **Best for**: Quick start, CI/CD, and cases where port 80 is unavailable.

### Commands
```bash
devhost start     # Starts the Gateway router
devhost status    # Checks if the router is healthy
devhost stop      # Stops the router
```

### Optional LAN access (opt-in)
```bash
devhost proxy expose --lan                 # Bind to 0.0.0.0
devhost proxy expose --iface 192.168.1.10  # Bind to a specific IPv4
devhost proxy expose --local               # Roll back to localhost-only
```
After changing bind addresses, restart the router: `devhost stop && devhost start`.

---

## Mode 2: System (Managed Caddy)

**Goal**: Full production parity with portless URLs.

- **How it works**: Devhost manages a dedicated [Caddy](https://caddyserver.com/) instance that binds to the standard HTTP (80) and HTTPS (443) ports.
- **URL Pattern**: `http://<name>.<domain>` (e.g., `http://api.localhost`).
- **Permissions**: Requires a one-time administrator elevation to bind to privileged ports.
- **Binding**: Localhost-only by default (`127.0.0.1`).
- **Best for**: Realistic cookie testing, complex OAuth flows, and professional demos.

### Commands
```bash
devhost proxy upgrade --to system  # Switch to System mode
devhost proxy start                # Start the managed Caddy process
devhost proxy status               # Check Caddy health and PID
```

If you change bind addresses with `devhost proxy expose`, reload Caddy:
```bash
devhost proxy reload
```

---

## Mode 3: External (Infrastructure Integration)

**Goal**: Integration with existing Nginx, Traefik, or Caddy setups.

- **How it works**: Devhost generates deterministic configuration snippets based on your routes. You can then "attach" these snippets to your existing proxy configuration using a minimal include/import block.
- **Ownership**: You remain the owner of your proxy's lifecycle. Devhost only provides the route definitions.
- **Drift Protection**: Uses manifests + integrity hashing to warn you if your proxy configuration or snippets changed manually.
- **Best for**: Teams with pre-existing complex proxy setups or shared development servers.

### Commands
```bash
devhost proxy export --driver nginx  # Generate a snippet
devhost proxy attach nginx --config-path /etc/nginx/nginx.conf
devhost proxy drift --validate       # Explain drift and how to fix it
devhost proxy lock write             # Write a reproducible lockfile
devhost proxy sync --watch           # Re-export on route changes
```

### External Mode Features
- **Deterministic exports**: Stable ordering and whitespace for clean diffs.
- **Include-based attachment**: A small managed block inserts a single include/import line.
- **Validation hooks**: `devhost proxy validate` runs native validators (nginx, caddy, traefik).
- **Emergency reset**: `devhost proxy detach` removes only Devhost's managed block (with backups).
- **Multi-upstream support**: External exports can include `tcp`, `lan`, `docker`, and `unix` upstreams.
- **Lockfile**: `~/.devhost/devhost.lock.json` pins routes + driver settings for teams.

---

## Off

**Goal**: Route management without proxying.

- **How it works**: Devhost purely stores the mapping from subdomain to port/URL. No router or proxy is started.
- **Use case**: You just want to use `devhost list` as a bookmark manager for your local ports.

---

## Switching Modes

You can switch between Gateway and System modes using the `upgrade` command:

```bash
# Move to System mode (portless)
devhost proxy upgrade --to system

# Move back to Gateway mode (port 7777)
devhost proxy upgrade --to gateway
```
