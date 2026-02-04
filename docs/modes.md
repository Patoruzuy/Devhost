# Modes

Devhost supports multiple proxy “modes”. Only one mode is active at a time; the current mode lives in `~/.devhost/state.yml`.

## Mode 1: Gateway (default)

Goal: **work immediately** without admin privileges.

- You run a single local router on `127.0.0.1:7777`.
- Every app is reached via a subdomain + the gateway port: `http://api.localhost:7777`.

Commands:

```bash
devhost start
devhost stop
devhost status
```

## Mode 2: System (managed Caddy)

Goal: **portless URLs** (production parity): `http://api.localhost`.

- Devhost generates and runs a Caddy config that binds to `:80` (and optionally `:443`).
- Requires admin rights to bind privileged ports / adjust hosts on some setups.

Commands:

```bash
devhost proxy upgrade --to system
devhost proxy status
devhost proxy stop
```

## Mode 3: External (your existing proxy)

Goal: integrate into existing nginx/Traefik/Caddy setups **without breaking ownership boundaries**.

- Devhost generates snippets.
- You can *attach* snippets into a user-owned config (explicit + reversible).
- Integrity hashing helps detect drift.

Commands:

```bash
devhost proxy export --driver nginx
devhost proxy attach nginx --config-path /etc/nginx/nginx.conf
devhost proxy detach --config-path /etc/nginx/nginx.conf
```

## Off

Goal: disable proxying and use direct upstreams.

- Routes can still be stored, but access is direct (e.g. `http://127.0.0.1:8000`).

## Switching modes

```bash
devhost proxy upgrade --to gateway
devhost proxy upgrade --to system
```

When switching to/from System mode, Devhost may start/stop Caddy depending on route presence and conflicts.

