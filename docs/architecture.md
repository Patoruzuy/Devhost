# Architecture Overview

Devhost is split into a few clear responsibilities:

## CLI (`devhost`)

- Manages routes (`~/.devhost/devhost.json`)
- Manages v3 state (`~/.devhost/state.yml`) for modes, integrity, and proxy metadata
- Provides diagnostics (`validate`, `doctor`) and helpers (`qr`, `oauth`, `env sync`)

## Gateway router (Mode 1)

- FastAPI app that proxies HTTP and WebSocket traffic based on the `Host` header.
- Listens on a single port (default `7777`) and fans out to upstream targets.
- Reads routes from `DEVHOST_CONFIG` or `~/.devhost/devhost.json`.

## System proxy (Mode 2)

- Managed Caddy process that binds to `:80` / `:443`.
- Devhost generates a Mode-2 Caddyfile under `~/.devhost/proxy/caddy/Caddyfile`.

## External proxy integration (Mode 3)

- Generates snippets for Caddy/nginx/Traefik.
- Optional attach/detach flows are explicit, reversible, and tracked with integrity hashes.

## Integrity hashing

Files Devhost writes/owns can be tracked with SHA-256 hashes in `state.yml`:

- protects user-owned config from accidental corruption
- helps detect drift when configs are edited manually

