# Devhost

![CI](https://github.com/Patoruzuy/Devhost/actions/workflows/ci.yml/badge.svg)
![Release](https://img.shields.io/github/v/release/Patoruzuy/Devhost)

**Secure, flexible local domain routing for developers.**

Devhost allows you to map subdomains of a base domain (default: `localhost`, e.g. `myapp.localhost`) to local app ports, with automatic HTTPS and wildcard routing via Caddy and a Python backend.

## Features

- Map domains like `app.localhost` → `localhost:1234`
- HTTPS support via Caddy's internal CA (use `--https`)
- Add/remove routes using a single CLI command
- Wildcard reverse proxy using Python (FastAPI)
- Custom base domain (e.g. `hello.flask`)
- Supports macOS, Linux, and Windows (native PowerShell shim)

## Benefits for Devs

- No need to remember localhost:PORT combos
- Clean and memorable dev URLs
- HTTP by default; HTTPS available with `--https`
- Works with any language/framework running locally

## Quickstart

### 1. Clone the project

```bash
git clone https://github.com/Patoruzuy/devhost.git
./install.sh
devhost add hello 3000
devhost list
devhost remove hello
```

Visit `hello.localhost` in your browser.

Note: the `devhost` CLI is now implemented in Python (cross-platform). The prior bash script is kept as `devhost.sh` for reference during the migration.

Cross-platform installer (uses the Python CLI):

```bash
python install.py --linux
```

To change the base domain (for example, `hello.flask`), set it once and re-run your installer to update DNS/resolvers:

```bash
devhost domain flask
./install.sh --domain flask
```

Run the router locally (development):

```bash
cd router
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 5555 --reload
```

Run the router in Docker (quick):

```bash
docker compose up --build -d
# then open http://127.0.0.1:5555 with Host header set to <name>.localhost
```

`docker-compose.yml` mounts the repo `devhost.json` into the container so edits take effect immediately.

Notes & safety

- `install.sh` is Debian/Ubuntu-oriented and will prompt you about DNS changes. Review DNS/resolver changes before applying them on systems using `systemd-resolved`.
- We now generate the project `caddy/Caddyfile`, the user `~/.config/caddy/Caddyfile`, and (if present) `/etc/caddy/Caddyfile` to keep system Caddy installs in sync.
- The router loads `devhost.json` per request so CLI changes take effect immediately without restarting the router.

Quick Commands

- `devhost add <name> <port|host:port>` — add a mapping (e.g. `devhost add hello 3000`).
- `devhost add <name> --http <port|host:port>` — force HTTP when opening the dev URL.
- `devhost add <name> --https <port|host:port>` — force HTTPS when opening the dev URL.
- `devhost remove <name>` — remove a mapping.
- `devhost list` — show active mappings.
- `devhost list --json` — show mappings as JSON.
- `devhost url <name>` — print the URL and press Ctrl+O to open it in the browser.
- `devhost open <name>` — open the URL in the default browser.
- `devhost validate` — quick health checks (config JSON, router health, DNS).
- `devhost export caddy` — print the generated Caddyfile to stdout.
- `devhost edit` — open `devhost.json` in `$EDITOR` (fallback: `nano`/`vi`).
- `devhost resolve <name>` — show DNS resolution and port reachability for a mapping.
- `devhost doctor` — deeper diagnostics (dnsmasq/systemd-resolved/Caddy).
- `devhost doctor --windows` — Windows-specific diagnostics (Caddy, port 80, hosts).
- `devhost doctor --windows --fix` — attempt Windows fixes (hosts sync + free port 80 + start Caddy).
- `devhost info` — show all commands and usage.
- `devhost status --json` — print router status as JSON (running, pid, health).
- `devhost domain [name]` — show or set the base domain (default: `localhost`).
- `devhost hosts sync` — re-apply hosts entries for all mappings on Windows (admin).
- `devhost hosts clear` — remove all devhost entries from the Windows hosts file (admin).
- `devhost caddy start|stop|restart|status` — manage Caddy on Windows.


## How It Works

Devhost consists of two components:

1. **Router** - A FastAPI app that proxies requests based on subdomain
2. **CLI** - Python script to manage configuration

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ http://myapp.localhost
       │
┌──────▼────────┐
│ Devhost Router│ :5555
│  (localhost)  │
└──────┬────────┘
       │ Routing based on subdomain
       │
┌──────▼────────┐
│   Your App    │ :3000
│  (localhost)  │
└───────────────┘
```

Configuration

The project uses a `devhost.json` file (project root) with a simple mapping of names to ports. Example:

```json
{
	"hello": 3000,
	"api": 8000
}
```

This file is created/updated by the CLI and is meant to be local (it’s gitignored). The router reads `DEVHOST_CONFIG` if set; otherwise it looks for the project root `devhost.json` (even when run from `router/`). The base domain comes from `DEVHOST_DOMAIN` or `.devhost/domain` (default: `localhost`).

Router endpoints

- `GET /health` — liveness + route count + uptime.
- `GET /metrics` — basic request metrics (totals, per-status, per-subdomain).
- `GET /routes` — current routes with parsed targets.
- `GET /mappings` — current routes with basic TCP health checks.

Logging

- `DEVHOST_LOG_LEVEL` controls router log verbosity (default: `INFO`).
- `DEVHOST_LOG_FILE` writes logs to a file in addition to stdout.
- `DEVHOST_LOG_REQUESTS=1` enables per-request logging.

Quick test (curl)

Run the router (locally or via Docker) and test with `curl` by setting the `Host` header:

```bash
curl -H "Host: hello.localhost" http://127.0.0.1:5555/
```

Regenerating Caddyfile

The `devhost` CLI writes both the project `caddy/Caddyfile` (generated, gitignored) and, when present, the user `~/.config/caddy/Caddyfile`. Inspect generated files before reloading system Caddy and, when appropriate, reload the service:

```bash
# inspect
less caddy/Caddyfile
# if using system Caddy (Linux)
sudo systemctl reload caddy
```

Troubleshooting

- Check mappings: `devhost list`.
- Router health: `curl http://127.0.0.1:5555/health` should return `{ "status": "ok" }`.
- If DNS/resolver issues on Linux, check `systemd-resolved` and `/etc/resolv.conf` for unintended changes.
- Ensure Caddy is running if you depend on system TLS (check `systemctl status caddy`).

Platform notes

- `install.sh` targets Debian/Ubuntu systems; it reads `DEVHOST_DOMAIN` or `.devhost/domain` to configure DNS for the base domain.
- Windows setup is supported via `scripts/setup-windows.ps1` (see below). If you change the base domain on Windows, run PowerShell as Administrator so Devhost can add hosts entries automatically, or use a local DNS resolver (Acrylic) for wildcard domains.

Release notes

See `CHANGELOG.md` for the v1.0.0 release notes.

macOS installer

- An interactive installer script is available at `scripts/setup-macos.sh`. It generates a LaunchAgent plist from `router/devhost-router.plist.tmpl`, creates `/etc/resolver/<domain>` pointing to `127.0.0.1`, and can optionally start `dnsmasq` via Homebrew and load the LaunchAgent.
- The installer accepts either a uvicorn binary path or `python3 -m uvicorn` and generates a valid LaunchAgent accordingly.
- The installer can optionally install shell completions to `~/.zsh/completions` and `~/.bash_completion.d`.

Usage examples:

```bash
# dry-run (print actions)
bash scripts/setup-macos.sh --dry-run

# run interactively (will prompt for username and uvicorn path)
bash scripts/setup-macos.sh
```

The script will prompt before making system changes and backs up any existing plist file it replaces.

Non-interactive example

You can run the installer non-interactively (accept all prompts and start dnsmasq if available) with:

```bash
# from repo root
devhost install --macos --yes
# or directly
bash scripts/setup-macos.sh --yes
```

If you want the script to also start dnsmasq automatically, pass `--start-dns`:

```bash
devhost install --macos --yes --start-dns
```

To use a custom base domain on macOS:

```bash
devhost domain flask
devhost install --macos --domain flask
```

Windows installer

Run the PowerShell setup script from Windows to prepare the venv, router deps, and initial config:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup-windows.ps1
```

To clean and reinstall:

```powershell
.\scripts\setup-windows.ps1 -Clean
```

The Windows installer prints next-step instructions for installing Caddy and running the router.
You can run the CLI from Windows PowerShell using the shim:

```powershell
.\devhost.ps1 add hello 8000
```

If you prefer the Python CLI, you can run:

```powershell
python .\devhost install --windows --caddy
python .\devhost add hello 8000
```

Note: the router requires a Host header. Don’t browse `http://127.0.0.1:5555` directly — use `devhost open <name>` or:

```powershell
curl -H "Host: hello.localhost" http://127.0.0.1:5555/

Tip (Windows): if your app only listens on IPv4, Devhost uses `127.0.0.1` for numeric ports to avoid IPv6 `::1` connection errors.
```

Tip: On Windows, `devhost.ps1 start` will try to start Caddy (if installed) before starting the router.
