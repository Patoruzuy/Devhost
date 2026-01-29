# Devhost

![CI](https://github.com/Patoruzuy/Devhost/actions/workflows/ci.yml/badge.svg)
![Release](https://img.shields.io/github/v/release/Patoruzuy/Devhost)

**Secure, flexible local domain routing for developers.**

Devhost allows you to map subdomains of `localhost` (e.g. `myapp.localhost`) to local app ports, with automatic HTTPS and wildcard routing via Caddy and a Python backend.

## Features

- Map domains like `app.localhost` → `localhost:1234`
- Serve via HTTPS using Caddy's internal CA
- Add/remove routes using a single CLI command
- Wildcard reverse proxy using Python (FastAPI)
- Supports macOS and Linux

## Quickstart

### 1. Clone the project

```bash
git clone https://github.com/YOURNAME/devhost.git
./install.sh
devhost add hello 3000
devhost list
devhost remove hello
```

Visit `hello.localhost` in your browser.

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

Notes & safety

- `install.sh` is Debian/Ubuntu-oriented and will prompt you about DNS changes. Review DNS/resolver changes before applying them on systems using `systemd-resolved`.
- We now generate both the project `caddy/Caddyfile` and, when present, the user `~/.config/caddy/Caddyfile` to keep local and system Caddy installs in sync.
- The router loads `devhost.json` per request so CLI changes take effect immediately without restarting the router.

Quick Commands

- `devhost add <name> <port>` — add a mapping (e.g. `devhost add hello 3000`).
- `devhost remove <name>` — remove a mapping.
- `devhost list` — show active mappings.

Configuration

The project uses a `devhost.json` file (project root) with a simple mapping of names to ports. Example:

```json
{
	"hello": 3000,
	"api": 8000
}
```

Quick test (curl)

Run the router (locally or via Docker) and test with `curl` by setting the `Host` header:

```bash
curl -H "Host: hello.localhost" http://127.0.0.1:5555/
```

Regenerating Caddyfile

The `devhost` CLI writes both the project `caddy/Caddyfile` and, when present, the user `~/.config/caddy/Caddyfile`. Inspect generated files before reloading system Caddy and, when appropriate, reload the service:

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

- `install.sh` targets Debian/Ubuntu systems; Windows is not supported by the install script — run the router in Docker on Windows.

Release notes

See `CHANGELOG.md` for the v1.0.0 release notes.

macOS installer

- An interactive installer script is available at `scripts/setup-macos.sh`. It generates a LaunchAgent plist from `router/devhost-router.plist.tmpl`, creates `/etc/resolver/localhost` pointing to `127.0.0.1`, and can optionally start `dnsmasq` via Homebrew and load the LaunchAgent.

Usage examples:

```bash
# dry-run (print actions)
bash scripts/setup-macos.sh --dry-run

# run interactively (will prompt for username and uvicorn path)
bash scripts/setup-macos.sh
```

The script will prompt before making system changes and backs up any existing plist file it replaces.
