# Configuration Deep Dive

Devhost uses a two-layer configuration system to balance project-specific needs with global system state.

## 1. Global State: `~/.devhost/state.yml`

This file is the "Brain" of Devhost. It tracks the current operational mode and integrity data.

### Key Fields

- **`proxy.mode`**: One of `off`, `gateway`, `system`, or `external`.
- **`proxy.gateway.listen`**: The address the router binds to (default `127.0.0.1:7777`). Prefer `devhost proxy expose --local|--lan|--iface <ip>` to change this safely.
- **`proxy.system.listen_http`**: HTTP bind address for System mode (default `127.0.0.1:80`).
- **`proxy.system.listen_https`**: HTTPS bind address for System mode (default `127.0.0.1:443`).
- **`proxy.external.driver`**: External proxy driver (`caddy`, `nginx`, `traefik`).
- **`proxy.external.config_path`**: Attached external proxy config path (if any).
- **`routes`**: A mirror of active routes, including metadata like `tags`, `enabled` status, custom `domain` overrides, and optional `upstreams`.
- **`routes.*.upstreams`**: Optional list of upstreams for External mode exports (`tcp`, `lan`, `docker`, `unix`).
- **`integrity.hashes`**: A map of SHA-256 hashes for all Devhost-managed files.

### Why a separate state file?
By separating state from the route list, Devhost can remember your preferences (like which proxy driver you use) even if you clear your route list or switch projects.

## 2. Route Definition: `devhost.json`

This is the "Source of Truth" for the actual mappings. By default, it lives in `~/.devhost/devhost.json`.

```json
{
  "api": 8000,
  "web": "127.0.0.1:3000",
  "docs": "https://docs.local:8443"
}
```

### Mapping formats
- **Integer**: Interpreted as `http://127.0.0.1:PORT`.
- **String (Host:Port)**: Interpreted as `http://HOST:PORT`.
- **String (Full URL)**: Preserves the specified scheme (e.g., `https://...`).

Note: Multi-upstream definitions are stored in `~/.devhost/state.yml` and the optional lockfile, not in `devhost.json`. Gateway/System modes always use the primary target.

## 3. Project Config: `devhost.yml`

Place this in your repository root to enable zero-config startup for your team.

```yaml
name: my-app
port: 0            # 0 = auto-detect free port
domain: localhost
auto_register: true
auto_caddy: false
```

When you use the `devhost_cli.runner.run()` helper, it will automatically:
1. Load this file.
2. Find an available port if `port: 0`.
3. Register the route with the global Devhost instance.
4. Start the router if it's not running.

## 4. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVHOST_CONFIG` | `~/.devhost/devhost.json` | Path to the routes JSON file. |
| `DEVHOST_DOMAIN` | `localhost` | The default base domain for all subdomains. |
| `DEVHOST_ALLOW_PRIVATE_NETWORKS` | `false` | Set to `1` to allow proxying to LAN IPs (SSRF bypass). |
| `DEVHOST_TIMEOUT` | `60` | Request timeout in seconds. |
| `DEVHOST_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `DEVHOST_LOG_REQUESTS` | `false` | Set to `1` to log every proxied request. |

## 5. Directory Structure

```text
~/.devhost/
├── state.yml           # Global state & mode
├── devhost.json        # Global routes
├── devhost.lock.json   # Optional lockfile (External mode)
├── domain              # Active base domain name
├── logs/               # Router and tunnel logs
├── backups/            # Backups created before attaching snippets
└── proxy/              # Mode 2 & 3 generated configurations
    ├── caddy/
    ├── nginx/
    └── traefik/
```
