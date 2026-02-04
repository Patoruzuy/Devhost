# Devhost v3.0 Plan — Safe by Default, Powerful by Choice

## Executive Summary

Devhost v3.0 optimizes for **developer trust** and **time-to-delight**:

- **Default onboarding = no admin, no system changes (Mode 1: Gateway)** to avoid port 80 conflicts and immediately reduce “port salad”.
- **Portless URLs (Mode 2: System Proxy / owned Caddy)** stay a first-class upgrade for teams that want `http://app.localhost` with no port.
- **External proxy support (Mode 3)** is a first-class integration via **snippet export + optional attach/detach**, never “owning” the user’s proxy.
- **Trust features move earlier** (Integrity Hashing / Drift Detection + “Panic Button”) because they are what makes developers comfortable enabling Advanced modes.

Rich CLI in Phase 1, Dashboard in Phase 5 /Dashboard.md, WebSocket/Tunnels in Phase 6.


---


## Implementation Phases (Revised)

| Phase | Weeks | Focus | Key Deliverables |
|-------|-------|-------|------------------|
| **1** | 1-2 | Config consolidation + Rich CLI + fix CI | Single config source, styled output, passing tests |
| **2** | 3-4 | Mode 2 polish | OAuth helper, QR codes, env sync |
| **3** | 5-6 | Mode 3: External proxy | Snippet generation, auto-import, `proxy transfer` |
| **4** | 7-8 | Caddy lifecycle + Windows | Ownership model, port 80 conflicts, better detection |
| **5** | 9-10 | Dashboard (Textual TUI) | Live routes, log tailing, interactive mode |
| **6** | 11-12 | WebSocket + Tunnels | WebSocket proxying, cloudflared/ngrok integration |

---

## Why This Is Better Than the Previous Draft

### 1) Lower friction on day 0 (while still reaching portless)
**Change:** Default to a no-admin path (Mode 1), make Mode 2 a one-command upgrade.

**Why better:** Port 80/443 binding, WSL/IIS conflicts, and elevation prompts are the fastest way to create a “this tool is flaky” reputation. A Gateway default gives immediate value, then Mode 2 becomes an intentional upgrade with clear tradeoffs.

### 2) Separation of concerns: “generate config” vs “touch user config”
**Change:** Split external-proxy workflows into:
- `export` = always safe (writes only Devhost-owned snippet files)
- `attach/detach` = explicitly opt-in (edits user config with backups + drift protection)

**Why better:** Avoids surprise edits and makes support/debugging deterministic. “Export is safe” becomes a guarantee.

### 3) Verified migrations instead of “hope it works”
**Change:** After `attach` / `transfer`, run **probe-based verification** using `Host:` header requests to the proxy listener before switching modes.

**Why better:** Prevents silent breakage and reduces rollback complexity.

### 4) Hardening of real-world proxy/DNS/port edge cases
**Change:**
- Don’t rely on `~` expansion inside proxy configs; use absolute paths.
- Prefer `127.0.0.1` upstreams over `localhost` to avoid IPv6-first surprises.
- Consolidate proxy config discovery into one interactive algorithm.

**Why better:** These are the “works on my machine” foot-guns that kill adoption.

---

## Product Principles (Non-Negotiables)

- **Never surprise-edit**: Any edit to user-owned files must be explicit, backed up, and reversible.
- **Clear ownership boundaries**: Devhost “owns” only what it created (snippets, its own state). Everything else is opt-in.
- **One mental model per mode**: Mode names must map to concrete user outcomes.
- **Prefer loopback by default**: Don’t accidentally expose services on LAN.
- **Trust first**: Drift detection + emergency reset are not “nice to have”; they make Advanced modes usable.

---

## Modes (User Mental Model)

### Mode 0 — Awareness Only
**What it is:** Devhost tracks apps and prints URLs; no proxy, no system changes.

**When it’s useful:** Quick start, CI, “I just want a consistent CLI + bookmarks”.

### Mode 1 — Gateway (Default)
**What it is:** A single Devhost-managed proxy on an **unprivileged port** (e.g. `5480`).

**User experience:** You type one port forever:
- Frontend: `http://web.localhost:5480`
- API: `http://api.localhost:5480`

**Why this is the default:** It solves the real day-to-day pain (port salad) without admin or port 80 conflicts, and preserves cookie isolation via subdomains.

### Mode 2 — System Proxy (Portless Upgrade)
**What it is:** Devhost runs an owned Caddy (or equivalent) on `127.0.0.1:80/443` for portless URLs:
- `http://api.localhost` (no port)

**Tradeoff:** Requires elevated install and must handle port 80 conflicts cleanly.

### Mode 3 — External Proxy (Integration)
**What it is:** Devhost generates snippets for Caddy/Nginx/Traefik; optionally attaches them into a user-managed proxy config.

**Key rule:** Devhost never starts/stops the external proxy.

---

## Configuration Model (Consolidation)

### Goals
- **All generated assets live under `~/.devhost/`**
- **One canonical state file** for routes + metadata
- Project-local config stays optional (`./devhost.yml`) but should override defaults cleanly

### Proposed file layout
```
~/.devhost/
  state.yml
  backups/
    Caddyfile.20260203-103000.bak
  proxy/
    caddy/
      devhost.caddy
    nginx/
      devhost.conf
    traefik/
      devhost.yml
```

### Proposed schema (high level)
```yaml
version: 3

proxy:
  mode: gateway   # off|gateway|system|external

  gateway:
    listen: "127.0.0.1:5480"

  system:
    owned: true
    listen_http: "127.0.0.1:80"
    listen_https: "127.0.0.1:443"

  external:
    driver: caddy  # caddy|nginx|traefik
    config_path: "/etc/caddy/Caddyfile"
    snippet_path: "/absolute/path/to/.devhost/proxy/caddy/devhost.caddy"
    attach:
      auto_import: false
    reload:
      mode: manual  # manual|command
      command: "systemctl reload caddy"

integrity:
  enabled: true
  hashes:
    "/absolute/path/to/.devhost/proxy/caddy/devhost.caddy": "sha256:..."
    "/absolute/path/to/Caddyfile": "sha256:..."

routes:
  api:
    domain: "localhost"
    upstream: "127.0.0.1:3000"
    enabled: true
    tags: ["work"]
```

**Why better:** This removes config sprawl, makes troubleshooting deterministic, and enables Drift Detection without inventing a separate database.

---

## External Proxy Integration (Mode 3)

### 1) Snippet generation (always safe)
Write Devhost-owned snippets:
- Caddy: `~/.devhost/proxy/caddy/devhost.caddy`
- Nginx: `~/.devhost/proxy/nginx/devhost.conf`
- Traefik: `~/.devhost/proxy/traefik/devhost.yml`

**Important correctness defaults:**
- Use `127.0.0.1:<port>` for upstreams (avoid `localhost` IPv6 surprises).
- Include `Host` forwarding headers where relevant.

### 2) Attach / Detach (explicitly opt-in)
`devhost proxy attach`:
1. Discover candidate proxy config(s)
2. If multiple found, prompt user to choose
3. Backup the chosen file to `~/.devhost/backups/`
4. Insert an import/include block with markers
5. Optionally reload (only if user opted into a reload command)
6. Record hashes in state (Integrity Hashing)

**Caddy attach format (marker block):**
```caddy
# devhost: begin
import /absolute/path/to/.devhost/proxy/caddy/devhost.caddy
# devhost: end
```

`devhost proxy detach`:
- Remove the marked block only.
- If the block is missing or changed, treat as drift and prompt (don’t guess).

**Why better:** Reversible integration and deterministic cleanup are what make teams comfortable adopting Mode 3.

### 3) Discovery (single algorithm, interactive)
Search order (example):
```
devhost.yml:proxy.external.config_path
./Caddyfile
./caddy/Caddyfile
~/.config/caddy/Caddyfile
```
If nothing found: print next steps and still allow `export`.

---

## Mode 2 → Mode 3 Migration (`devhost proxy transfer`)

Command:
```bash
devhost proxy transfer --to external
```

Flow:
1. Generate snippets for all routes
2. Optionally attach into the external proxy config (backup + markers)
3. Reload (only if explicitly configured/confirmed)
4. **Verify** each route by probing the proxy listener with `Host:` headers
5. Only after verification: switch `proxy.mode` to `external`
6. Confirm with the user before stopping owned Caddy (Mode 2)

**Verification (minimum bar):**
- For each route, send a request to the external listener and confirm:
  - TCP connect works
  - HTTP response is non-error (or at least not a proxy-level failure)
  - Host routing resolves to the expected upstream

**Why better:** “Transfer” becomes a safe migration tool, not a leap of faith.

---

## Integrity Hashing / Drift Detection (Trust Feature)

### What we hash
Hash (SHA-256) any file Devhost writes or edits, including:
- `~/.devhost/proxy/**` snippets
- any user config file Devhost modified via `attach` (Caddyfile/Nginx conf/etc.)

### What happens on drift
If the file on disk doesn’t match the stored hash:
- Show a clear warning (CLI + TUI badge)
- Offer choices:
  - **Overwrite** (Devhost wins; re-render file)
  - **Preserve** (User wins; update stored hash)
  - **Abort** (safe default for scripts)

**Why better:** Prevents the “I fixed it manually and Devhost overwrote it” rage-quit moment that kills developer tools.

---

## Team Onboarding (“Shadow Mode”)

Allow projects to ship a repo-committed config file (example: `devhost.shared.yml`) that Devhost can **import** into the user’s local state/profile.

Rules:
- Repo config is **read-only** (Devhost never writes back to it).
- Import is explicit (CLI prompt / TUI modal), shows a **dry-run** of changes.
- Imported routes can be tagged into a profile (e.g., `work`, `client-a`).

**Why better:** “clone repo → accept prompt → everything routes correctly” is the fastest way to make Devhost feel like a real team tool, not just a personal convenience.

---

## CLI (Revised Command Surface)

```bash
# Core
devhost add <name> <upstream>     # upstream: <port> or <host:port>
devhost remove <name>
devhost list                      # Rich table
devhost open <name>
devhost url <name>
devhost status                    # current mode + health summary

# Setup
devhost init                      # minimal devhost.yml
devhost init --from-template      # full template

# Developer Experience (Phase 2)
devhost qr [name]                 # QR code for LAN access (optional)
devhost oauth [name]              # Print OAuth redirect URIs (optional)
devhost env sync                  # Sync .env with current URL (optional)

# Mode 1: Gateway (default)
devhost gateway start
devhost gateway stop
devhost gateway status

# Mode 2: System proxy (owned)
devhost proxy install --system    # explicit elevation step
devhost proxy system start
devhost proxy system stop
devhost proxy system status

# Mode 3: External proxy
devhost proxy export caddy|nginx|traefik
devhost proxy attach
devhost proxy detach
devhost proxy transfer --to external

# Trust & diagnostics
devhost doctor
devhost integrity check
devhost reset --hard              # “panic button”

# Future
devhost dashboard                 # Textual TUI
devhost tunnel start             # Start tunneling provider
devhost tunnel stop              # Stop tunneling provider
```

---

## Rich CLI (Phase 1) — What “Done” Looks Like

The earlier draft had “Merge Rich CLI into Phase 1” as an explicit step. That intent remains: Phase 1 ships a CLI that feels premium even before the proxy features get fancy.

### Dependencies (planned)
Add to `pyproject.toml` (or as an optional extra if you want to keep the base install minimal):
```toml
dependencies = [
  "click>=8.0",
  "rich>=13.0",
  "rich-click>=1.7",
  "segno>=1.6",  # QR codes (Phase 2 feature, but lightweight)
]
```

### CLI quality bar
- `devhost list`: rich table with mode badges, URL, upstream, integrity/drift, last probe result.
- `devhost doctor`: grouped sections with best-next-action suggestions (not just raw facts).
- `devhost proxy attach/transfer`: always prints a dry-run summary + rollback instructions.

---

## Error Handling & Rollback (Explicit)

This was spelled out in the earlier plan; it should remain explicit because these commands touch networking and configs.

### `devhost proxy attach`
- No config discovered → abort; print discovery order and recommend `devhost proxy export …`.
- Multiple configs discovered → prompt user to choose; never guess.
- Backup failure → abort (don’t attempt edits).
- Insert/import failed → restore backup; keep state unchanged.
- Reload configured but fails → restore backup; keep state unchanged; print captured stdout/stderr.
- Integrity drift detected before edit → prompt (Overwrite / Preserve / Abort). Default is Abort for scripting.

### `devhost proxy detach`
- Marker block not found → treat as drift; prompt (Abort / force-remove best-effort).
- File changed since last attach (hash mismatch) → prompt; default Abort.
- Detach succeeds but reload fails → restore backup and re-attach marker block.

### `devhost proxy transfer --to external` (Mode 2 → Mode 3)
- External proxy not reachable / cannot verify listener → abort; keep Mode 2 running.
- Attach fails → rollback; keep Mode 2 running.
- Verification probes fail → rollback and keep Mode 2; show per-route failures.
- Only after probes pass: switch `proxy.mode` to external; then (with confirmation) stop owned proxy.

### `devhost proxy install --system` (Mode 2)
- Requires elevation → explicit messaging; never auto-escalate from TUI.
- Port 80/443 conflicts → show owner process and best-next-action (stop, switch to Gateway, or external mode).

---

## Proxy Config Discovery (Mode 3)

### Discovery order
1. `devhost.yml` → `proxy.external.config_path` (project override)
2. Project-local:
   - `./Caddyfile`
   - `./caddy/Caddyfile`
   - `./nginx.conf`
   - `./conf.d/*.conf`
   - `./traefik.yml`
   - `./traefik/traefik.yml`
3. User-level defaults (driver-specific):
   - Caddy: `~/.config/caddy/Caddyfile`

If no config is found, the CLI prints:
```
⚠️  No proxy config found.
    You can still export snippets:
      devhost proxy export caddy

    Or set it in devhost.yml:
      proxy:
        mode: external
        external:
          driver: caddy
          config_path: /path/to/Caddyfile
```

---

## Caddy Attach Mechanics (Mode 3, driver=caddy)

### Snippet file (Devhost-owned)
Write: `~/.devhost/proxy/caddy/devhost.caddy`

Example:
```caddy
# Devhost-generated routes - do not edit manually
# Regenerated on every route change

myapp.localhost {
  reverse_proxy 127.0.0.1:8000
}
```

### Attach strategy (user-owned Caddyfile)
1. Resolve absolute snippet path (do not rely on `~` expansion).
2. Detect existing Devhost marker block:
   ```caddy
   # devhost: begin
   import /absolute/path/to/.devhost/proxy/caddy/devhost.caddy
   # devhost: end
   ```
3. If absent, prompt user to append the marker block (with backup).
4. Hash and record both files in `~/.devhost/state.yml`.

---

## Implementation Phases (Updated)

| Phase | Weeks | Focus | Key Deliverables |
|------:|:-----:|-------|------------------|
| **1** | 1-2 | Foundations + Trust | Config consolidation to `~/.devhost/`, unified `proxy:` schema, Integrity Hashing (CLI), Rich CLI |
| **2** | 3-4 | Mode 1 (Gateway default) | Single gateway port routing, better `doctor` guidance, IPv4-safe upstream defaults |
| **3** | 5-6 | Mode 2 (System Proxy upgrade) | Owned Caddy lifecycle, loopback-only binding, Windows port 80 conflict strategy |
| **4** | 7-8 | Mode 3 (External integration) | Export + attach/detach + transfer with verification probes |
| **5** | 9-10 | Dashboard (Textual TUI) | SessionState + Apply workflow, drift badges, ghost port detection, panic button |
| **6** | 11-12 | Advanced | WebSocket proxying + tunnel providers |

---

## Template File (`~/.devhost/devhost.template.yml`)

Installed on first run; `devhost init --from-template` copies it to project.

**Important addition vs prior draft:** template reflects the unified `proxy:` tree (not split `external_proxy` vs `proxy`), and calls out safety defaults (loopback binding, reload command opt-in).

Minimum recommended template skeleton:
```yaml
# Devhost Project Configuration (Template)
# Copy to your project as devhost.yml and uncomment what you need.

# name: myapp
# domain: localhost

proxy:
  # off|gateway|system|external
  mode: gateway

  gateway:
    listen: "127.0.0.1:5480"

  system:
    owned: true
    listen_http: "127.0.0.1:80"
    listen_https: "127.0.0.1:443"

  external:
    driver: caddy
    # config_path: /path/to/Caddyfile
    # snippet_path: /absolute/path/to/.devhost/proxy/caddy/devhost.caddy
    attach:
      auto_import: false
    reload:
      mode: manual  # manual|command
      # command: "systemctl reload caddy"

integrity:
  enabled: true
```

Installation UX:
- `devhost init` → creates minimal `devhost.yml`
- `devhost init --from-template` → copies full template to project

---

## Files to Modify (Likely)

This section existed in the earlier draft; keeping it helps implementation planning and PR sizing.

- `pyproject.toml` (Rich CLI deps; optional extras)
- `devhost_cli/cli.py` (new subcommands: gateway/proxy attach/detach/transfer; rich output)
- `devhost_cli/config.py` (unified state + proxy schema; discovery order)
- `devhost_cli/caddy.py` (snippet generation, attach markers, backups)
- `devhost_cli/utils.py` (hashing helpers, LAN IP detection, QR generation)
- `devhost_cli/windows.py` (port 80 conflict handling + best-next-action diagnostics)

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Time to first value (Mode 1) | < 30 seconds |
| Time to portless URL (Mode 2) | < 2 minutes (one-time setup) |
| “Surprise edits” | 0 (all edits are opt-in + backed up) |
| Drift handling | Detect + prompt (no silent overwrite) |
| Port 80 conflicts | `devhost doctor` gives best-next-action |
