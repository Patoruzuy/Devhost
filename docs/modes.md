# Proxy Modes

Devhost supports three active proxy modes and an "Off" state. The active mode is stored globally in `~/.devhost/state.yml`.

## Mode 1: Gateway (Default)

**Goal**: Immediate value with zero system configuration.

- **How it works**: Devhost starts a lightweight FastAPI-based router on port `7777`.
- **URL Pattern**: `http://<name>.<domain>:7777` (e.g., `http://api.localhost:7777`).
- **Permissions**: No administrator or root privileges required.
- **Best for**: Quick start, CI/CD, and cases where port 80 is unavailable.

### Commands
```bash
devhost start     # Starts the Gateway router
devhost status    # Checks if the router is healthy
devhost stop      # Stops the router
```

---

## Mode 2: System (Managed Caddy)

**Goal**: Full production parity with portless URLs.

- **How it works**: Devhost manages a dedicated [Caddy](https://caddyserver.com/) instance that binds to the standard HTTP (80) and HTTPS (443) ports.
- **URL Pattern**: `http://<name>.<domain>` (e.g., `http://api.localhost`).
- **Permissions**: Requires a one-time administrator elevation to bind to privileged ports.
- **Best for**: Realistic cookie testing, complex OAuth flows, and professional demos.

### Commands
```bash
devhost proxy upgrade --to system  # Switch to System mode
devhost proxy start                # Start the managed Caddy process
devhost proxy status               # Check Caddy health and PID
```

---

## Mode 3: External (Infrastructure Integration)

**Goal**: Integration with existing Nginx, Traefik, or Caddy setups.

- **How it works**: Devhost generates configuration snippets based on your routes. You can then "attach" these snippets to your existing proxy configuration.
- **Ownership**: You remain the owner of your proxy's lifecycle. Devhost only provides the route definitions.
- **Drift Protection**: Uses integrity hashing to warn you if your proxy configuration has changed manually in a way that conflicts with Devhost.
- **Best for**: Teams with pre-existing complex proxy setups or shared development servers.

### Commands
```bash
devhost proxy export --driver nginx  # Generate a snippet
devhost proxy attach nginx --config-path /etc/nginx/nginx.conf
```

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

