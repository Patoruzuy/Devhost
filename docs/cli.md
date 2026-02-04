# CLI Reference

Devhost is a single binary/entrypoint: `devhost`.

For the authoritative list of commands and flags:

```bash
devhost --help
devhost <command> --help
```

## Core workflow (Gateway mode)

```bash
devhost start                 # start the Gateway router (default mode)
devhost add api 8000          # register a route
devhost open api              # open http://api.localhost:7777
devhost list                  # show all routes
devhost stop                  # stop the Gateway router
```

## Core commands

- `devhost add <name> <target>`: `<target>` can be a port (`8000`), `host:port`, or a full URL (`https://host:port`).
- `devhost remove <name>`
- `devhost list [--json]`
- `devhost url [name]`
- `devhost open [name]`
- `devhost start` / `devhost stop`
- `devhost status`
- `devhost validate`
- `devhost doctor`
- `devhost logs [--follow] [--lines N] [--clear]`

## Domain & DNS

```bash
devhost domain get
devhost domain set home
```

Notes:
- `localhost` is the easiest base domain (no extra DNS/hosts configuration on most systems).
- For custom domains (e.g. `home`, `lab`, `dev`), you’ll likely need to configure DNS/hosts. See [Configuration](configuration.md#dns--domains).

## Proxy modes (System / External)

Mode management:

```bash
devhost proxy upgrade --to system
devhost proxy upgrade --to gateway
```

System proxy (Mode 2):

```bash
devhost proxy start
devhost proxy status
devhost proxy reload
devhost proxy stop
```

External proxy (Mode 3):

```bash
devhost proxy export --driver caddy
devhost proxy export --driver nginx
devhost proxy export --driver traefik

devhost proxy discover
devhost proxy attach caddy --config-path /path/to/Caddyfile
devhost proxy detach --config-path /path/to/Caddyfile
devhost proxy transfer caddy --config-path /path/to/Caddyfile
```

See [External Proxy Integration](external-proxy.md) for safe-by-default behavior and drift protection.

## Tunnels

```bash
devhost tunnel start api --provider cloudflared
devhost tunnel status
devhost tunnel stop api
```

Tunnels use external CLIs; see [Tunnels](tunnels.md).

## Dashboard (TUI)

```bash
pip install devhost[tui]
devhost dashboard
```

See [Dashboard](dashboard.md).

