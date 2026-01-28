# Devhost

**Secure, flexible local domain routing for developers.**

Devhost allows you to map subdomains of `localhost` (e.g. `myapp.localhost`) to local app ports, with automatic HTTPS and wildcard routing via Caddy and a Python backend.

## Features

- Map domains like `app.localhost` → `localhost:1234`
- Serve via HTTPS using Caddy's internal CA
- Add/remove routes using a single CLI command
- Wildcard reverse proxy using Python (FastAPI)
- Supports macOS and Linux

## Quickstart

```bash
./install.sh
devhost add hello 3000
devhost list
devhost remove hello

Visit hello.localhost 

in your browser!
""",
"install.sh": """
#!/bin/bash

# Devhost

Secure, flexible local domain routing for developers.

Devhost maps subdomains of localhost (for example `myapp.localhost`) to local application ports. It uses:

- Caddy for TLS and wildcard proxying
- A small FastAPI router for per-subdomain reverse-proxying

Supported OS: Linux (Debian/Ubuntu tested). macOS may work with adjustments. Windows is not supported out of the box.

Quickstart

```bash
./install.sh
devhost add hello 3000
devhost list
devhost remove hello
```

Run the router locally (development):

```bash
cd router
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 5555 --reload
```

Notes & safety

- `install.sh` is Debian/Ubuntu-oriented and will prompt you about DNS changes. Review DNS/resolver changes before applying them on systems using `systemd-resolved`.
- We now generate both the project `caddy/Caddyfile` and, when present, the user `~/.config/caddy/Caddyfile` to keep local and system Caddy installs in sync.
- The router loads `devhost.json` per request so CLI changes take effect immediately without restarting the router.

If you want, I can now run a quick syntax check and a smoke test of the router in this environment, or open a PR with these changes.