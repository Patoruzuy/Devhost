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

## Benefits for Devs

- No need to remember localhost:PORT combos
- Clean and memorable dev URLs
- Auto-HTTPS with Caddy (tls internal)
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
- We now generate both the project `caddy/Caddyfile` and, when present, the user `~/.config/caddy/Caddyfile` to keep local and system Caddy installs in sync.
- The router loads `devhost.json` per request so CLI changes take effect immediately without restarting the router.

Quick Commands

- `devhost add <name> <port>` — add a mapping (e.g. `devhost add hello 3000`).
- `devhost remove <name>` — remove a mapping.
- `devhost list` — show active mappings.
- `devhost url <name>` — print the HTTPS URL and press Ctrl+O to open it in the browser.
- `devhost open <name>` — open the HTTPS URL in the default browser.
- `devhost validate` — quick health checks (config JSON, router health, DNS).
- `devhost export caddy` — print the generated Caddyfile to stdout.
- `devhost edit` — open `devhost.json` in `$EDITOR` (fallback: `nano`/`vi`).
- `devhost resolve <name>` — show DNS resolution and port reachability for a mapping.
- `devhost doctor` — deeper diagnostics (dnsmasq/systemd-resolved/Caddy).
- `devhost info` — show all commands and usage.
- `devhost status --json` — print router status as JSON (running, pid, health).

Configuration

The project uses a `devhost.json` file (project root) with a simple mapping of names to ports. Example:

```json
{
	"hello": 3000,
	"api": 8000
}
```

The router reads `DEVHOST_CONFIG` if set; otherwise it looks for the project root `devhost.json` (even when run from `router/`).

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
