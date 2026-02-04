# Configuration

Devhost is intentionally file-based and transparent.

## Global state directory: `~/.devhost/`

Common files and folders:

- `~/.devhost/state.yml`: mode, proxy settings, integrity hashes, routes mirror
- `~/.devhost/devhost.json`: route source used by the gateway router
- `~/.devhost/logs/`: tunnel and router logs (when applicable)
- `~/.devhost/proxy/`: generated snippets and managed configs (Mode 2/3)
- `~/.devhost/backups/`: backups made during attach/detach/transfer (Mode 3)

### `state.yml` (v3)

Key fields (simplified):

```yaml
version: 3
proxy:
  mode: gateway  # off | gateway | system | external
  gateway:
    listen: "127.0.0.1:7777"
  system:
    domain: "localhost"
routes: {}
integrity:
  enabled: true
  hashes: {}
```

### `devhost.json` (routes)

Routes map subdomain → upstream target:

```json
{
  "api": 8000,
  "frontend": "127.0.0.1:3000",
  "remote": "192.168.1.50:8080",
  "secure": "https://127.0.0.1:8443"
}
```

## Project config: `devhost.yml` (optional)

Use this when you want per-repo defaults for the runner:

```yaml
name: myapp
port: 0            # 0 = auto-pick a free port
domain: localhost
auto_register: true
auto_caddy: false
```

Create it with:

```bash
devhost init
```

## Environment variables

- `DEVHOST_CONFIG`: override `devhost.json` location
- `DEVHOST_DOMAIN`: override base domain (`localhost` by default)
- `DEVHOST_LOG_LEVEL`: `DEBUG|INFO|WARNING|ERROR`
- `DEVHOST_LOG_REQUESTS`: `1/true/yes/on` to log per-request

## DNS & domains

### Recommended: `.localhost`

`localhost` is the easiest base domain for subdomains (e.g. `api.localhost`) because it typically resolves to loopback without extra setup.

### Custom base domains (e.g. `home`, `lab`)

If you set a non-`localhost` base domain, you need to make sure it resolves:

- **Windows**: `devhost hosts sync` (admin) or manage DNS in your network
- **macOS/Linux**: set up a local DNS resolver (e.g. `dnsmasq`) or use `/etc/hosts`

Devhost is intentionally conservative: it won’t silently reconfigure system DNS.

