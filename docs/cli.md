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

- `devhost add <name> <target> [--upstream <type:target> ...]`: The target can be a port (`8000`), a host:port (`192.168.1.10:8000`), or a full URL (`https://app.external.com`). Additional upstreams are stored for External mode exports. Types: `tcp`, `lan`, `docker`, `unix`.
- `devhost remove <name>`: Deletes the route from configuration.
- `devhost edit`: Opens the raw `devhost.json` mapping file in your default editor.
- `devhost list [--json]`: Lists all routes. Use `--json` for automation.

## Discovery & Health

- `devhost status`: Shows the current proxy mode, router health, and a summary of active routes.
- `devhost doctor`: Per-platform diagnostic utility that checks for port conflicts, binary availability, and configuration errors.
- `devhost validate`: Checks if the upstream services for your routes are actually responding.
- `devhost logs [-f]`: Tails the logs for the router and active processes.

## Dashboard (Interactive TUI)

Launch the visual dashboard for interactive management:

```bash
devhost dashboard
```

**Key Features:**
- Press `F1` for complete keyboard shortcuts
- Press `A` to add routes with guided wizard
- Press `D` to delete (with confirmation)
- `Ctrl+S` to apply draft changes
- `Ctrl+P` to probe route health
- `/` for command palette with autocomplete

See [Dashboard Documentation](dashboard.md) for full feature list.

## Installer (Optional)

The installer helper performs opt-in setup steps with confirmation:

```bash
devhost install --caddy                # Install Caddy if possible
devhost install --install-completions  # Install shell completions
devhost install --domain mydev.local   # Set default domain
devhost install --dry-run              # Show what would happen
```
Use `--yes` to skip confirmations.

## Proxy Mode Switching (System / External)

```bash
devhost proxy upgrade --to system    # Switch to portless URLs (port 80)
devhost proxy upgrade --to gateway   # Switch back to port 7777
```

## LAN Access (Opt-in)

Bind Devhost to the LAN when you explicitly need other devices to access it.

```bash
devhost proxy expose --lan                 # Bind to 0.0.0.0 (all interfaces)
devhost proxy expose --iface 192.168.1.10  # Bind to a specific interface (IPv4)
devhost proxy expose --local               # Restore localhost-only binding
```

After changing bind addresses, restart the router (`devhost stop && devhost start`).
If you are in System mode, also run `devhost proxy reload`.

## System Mode (Managed Caddy)

- `devhost proxy start`: Starts the managed Caddy instance.
- `devhost proxy stop`: Stops Caddy.
- `devhost proxy status`: Shows Caddy process information (PID, uptime).

## External Proxy Integration

- `devhost proxy export --driver [nginx|caddy|traefik] [--use-lock --lock-path <path>]`: Prints or saves a configuration snippet for use in your own proxy.
- `devhost proxy attach <driver> --config-path <path> [--no-validate --use-lock --lock-path <path>]`: Safely injects the Devhost snippet into your existing configuration file.
- `devhost proxy detach --config-path <path> [--force]`: Removes the Devhost-injected block from your configuration.
- `devhost proxy drift [--driver <driver>] [--config-path <path>] [--validate]`: Detects drift between managed snippets and your proxy config.
- `devhost proxy drift --accept`: Accepts current files as the new baseline.
- `devhost proxy validate [--driver <driver>] --config-path <path>`: Runs the proxy's native config validator.
- `devhost proxy lock write|apply|show [--path <path>]`: Manage the lockfile (`~/.devhost/devhost.lock.json` by default).
- `devhost proxy sync [--driver <driver>] [--watch] [--use-lock]`: Re-export snippets when routes change.
- `devhost proxy cleanup --system|--external|--lock|--all`: Remove Devhost-managed proxy files (does not touch your proxy config).

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
- `devhost hosts restore`: Restores the Windows `hosts` file from the `.bak` rollback backup (requires Administrator privileges; confirmation prompt unless `--yes`).

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
