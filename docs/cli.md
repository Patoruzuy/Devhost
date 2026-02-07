# CLI Reference

Devhost is controlled via a single command-line tool: `devhost`.

For the authoritative list of commands and flags:

```bash
devhost --help
devhost <command> --help
```

## Basic Workflow (Gateway Mode)

The default mode when you first install Devhost.

```bash
devhost start                 # Start the Gateway router (port 7777)
devhost add web 3000          # Map http://web.localhost:7777 -> :3000
devhost list                  # Show all active routes
devhost open web              # Open the URL in your default browser
devhost stop                  # Shut down the router
```

## Route Management

- `devhost add <name> <target>`: The target can be a port (`8000`), a host:port (`192.168.1.10:8000`), or a full URL (`https://app.external.com`).
- `devhost remove <name>`: Deletes the route from configuration.
- `devhost edit`: Opens the raw `devhost.json` mapping file in your default editor.
- `devhost list [--json]`: Lists all routes. Use `--json` for automation.

## Discovery & Health

- `devhost status`: Shows the current proxy mode, router health, and a summary of active routes.
- `devhost doctor`: Per-platform diagnostic utility that checks for port conflicts, binary availability, and configuration errors.
- `devhost validate`: Checks if the upstream services for your routes are actually responding.
- `devhost logs [-f]`: Tails the logs for the router and active processes.

## Proxy Mode Switching (System / External)

```bash
devhost proxy upgrade --to system    # Switch to portless URLs (port 80)
devhost proxy upgrade --to gateway   # Switch back to port 7777
```

## System Mode (Managed Caddy)

- `devhost proxy start`: Starts the managed Caddy instance.
- `devhost proxy stop`: Stops Caddy.
- `devhost proxy status`: Shows Caddy process information (PID, uptime).

## External Proxy Integration

- `devhost proxy export --driver [nginx|caddy|traefik]`: Prints or saves a configuration snippet for use in your own proxy.
- `devhost proxy attach <driver> --config-path <path>`: Safely injects the Devhost snippet into your existing configuration file.
- `devhost proxy detach --config-path <path>`: Removes the Devhost-injected block from your configuration.

## Tunnels

Expose a local route to the public internet using an external provider.

```bash
devhost tunnel start api --provider cloudflared
devhost tunnel status
devhost tunnel stop api
```

Supported providers: `cloudflared`, `ngrok`, `localtunnel`.

## Windows-Specific Commands

- `devhost hosts sync`: Synchronizes your Devhost routes with the Windows `hosts` file (requires Administrator privileges).
- `devhost hosts clear`: Removes all Devhost-managed entries from the `hosts` file.

## TUI Dashboard

```bash
devhost dashboard
```
Requires the `[tui]` extra: `pip install devhost[tui]`.

```bash
devhost diagnostics export
devhost diagnostics export --output ./devhost-diagnostics.zip
devhost diagnostics export --no-logs --no-proxy
devhost diagnostics export --no-redact
devhost diagnostics export --max-size 50MB
devhost diagnostics export --no-size-limit
devhost diagnostics preview --no-logs --no-proxy
devhost diagnostics preview --top 10
devhost diagnostics preview --max-size 20MB
devhost diagnostics upload
devhost diagnostics export --redaction-file ./diagnostics-redaction.json
```

By default, secrets in logs/config/state files are redacted in the bundle.
Use `--no-redact` only when you explicitly need raw data.
Bundles enforce a default size limit (200MB). Use `--max-size` to override or
`--no-size-limit` to disable the cap.
You can supply custom redaction patterns with `--redaction-file` or by creating
`~/.devhost/diagnostics-redaction.json`.
You may also set `DEVHOST_DIAGNOSTICS_REDACTION_FILE` to override the path.

Example redaction file:

```json
{
  "redaction": {
    "include_defaults": true,
    "patterns": [
      {
        "pattern": "custom_secret=[^\\s]+",
        "replacement": "custom_secret=[REDACTED]"
      },
      {
        "pattern": "(?i)apikey\\s*[:=]\\s*\\S+",
        "replacement": "apikey=[REDACTED]",
        "flags": "i"
      }
    ]
  }
}
```
