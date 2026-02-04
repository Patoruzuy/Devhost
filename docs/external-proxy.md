# External Proxy Integration (Mode 3)

Mode 3 is designed for teams who already have a proxy (nginx/Traefik/Caddy) and want Devhost to *generate* and *safely integrate* config.

## Export snippets (no file edits)

```bash
devhost proxy export --driver caddy
devhost proxy export --driver nginx
devhost proxy export --driver traefik
```

Snippets are written under:

- `~/.devhost/proxy/caddy/devhost.caddy`
- `~/.devhost/proxy/nginx/devhost.conf`
- `~/.devhost/proxy/traefik/devhost.yml`

## Attach (explicit edit + reversible)

Attach inserts a marked block into a user-owned config file.

```bash
devhost proxy attach caddy --config-path /path/to/Caddyfile
```

Detach removes only the marked block:

```bash
devhost proxy detach --config-path /path/to/Caddyfile
```

## Drift detection (Integrity hashing)

Devhost tracks hashes of files it writes (snippets, managed configs, and backups) in `~/.devhost/state.yml` under `integrity.hashes`.

To verify:

```bash
devhost integrity check
```

If a file changed unexpectedly, Devhost can warn before destructive operations (transfer/reset flows).

## Transfer from Mode 2 → Mode 3

If you started with System mode (managed Caddy) and want to switch to External mode:

```bash
devhost proxy transfer caddy --config-path /path/to/Caddyfile
```

Transfer can:
- export snippets
- attach into your config (optional)
- verify routes (optional)
- switch the mode to `external`

