# Devhost TUI — Architecture

## Overview

The TUI is a Textual dashboard for the Devhost CLI. The CLI owns all
persistence (`devhost.json`, `state.yml`); the TUI is a read-heavy UI
layer that delegates writes through async bridge adapters.

```
┌─────────────────────────────────────────────────┐
│  app.py  (DevhostDashboard — ~400 LOC shell)    │
│  ┌────────┐  ┌───────────────────────────────┐  │
│  │Sidebar │  │  ContentSwitcher              │  │
│  │(Nav)   │  │  ┌─────────────────────────┐  │  │
│  │        │  │  │ RoutesScreen            │  │  │
│  │ 📋 Rts │  │  │ TunnelsScreen           │  │  │
│  │ 🔗 Tun │  │  │ ProxyScreen             │  │  │
│  │ ⚙ Prx │  │  │ DiagnosticsScreen       │  │  │
│  │ 🩺 Dgn │  │  │ SettingsScreen          │  │  │
│  │ 🔧 Set │  │  └─────────────────────────┘  │  │
│  └────────┘  └───────────────────────────────┘  │
│              Footer + CommandPalette             │
└─────────────────────────────────────────────────┘
         │              │               │
    services.py    cli_bridge.py    session.py
    (background)   (async CLI)     (draft state)
```

## Module Map

| File | LOC | Responsibility |
|------|-----|----------------|
| `app.py` | ~400 | Shell: compose, bindings, service wiring, message handlers |
| `widgets.py` | ~430 | NavSidebar, StatusGrid, FlowDiagram, IntegrityPanel, DetailsPane |
| `services.py` | ~450 | StateWatcher (watchdog), ProbeService, LogTailService, PortScanCache |
| `cli_bridge.py` | ~330 | Async wrappers: RouterBridge, TunnelBridge, ProxyBridge, FeaturesBridge, DiagnosticsBridge, ScannerBridge |
| `commands.py` | ~70 | CommandPalette Provider (20+ commands) |
| `session.py` | ~110 | SessionState: draft/apply pattern for route mutations |
| `wizard.py` | ~630 | 5-step AddRouteWizard (ModalScreen) |
| `modals.py` | ~1070 | All other modal dialogs |
| `screens/` | ~870 | Five screen Containers (routes, tunnels, proxy, diagnostics, settings) |

## Design Principles

1. **CLI is source of truth** — the TUI never writes `devhost.json` or
   `state.yml` directly. All writes go through `devhost_cli` functions
   wrapped by `cli_bridge.py`.

2. **Draft/Apply pattern** — `SessionState` holds in-memory route
   changes. Nothing persists until the user presses `Ctrl+S`
   (`action_apply_changes`), which calls `state.replace_state()`.

3. **ContentSwitcher, not screen push/pop** — all five screens are
   mounted once in `compose()`. Switching is instant via
   `switcher.current = screen_id`. No re-mount overhead.

4. **Modifier keybindings** — every binding uses a modifier combo
   (`ctrl+a`, `ctrl+d`, etc.) to avoid conflicts with text inputs.
   The only bare key is `q` (quit).

5. **Background services via Textual Messages** — services post
   `StateFileChanged`, `ProbeComplete`, `PortScanComplete` messages.
   The app catches them with `on_<message_class>()` handlers.

## Key Components

### `app.py` — DevhostDashboard

The main `App` subclass. Responsibilities:

- **Compose**: Header + Horizontal(NavSidebar + ContentSwitcher) + Footer
- **COMMANDS**: Registers `DevhostCommandProvider` for the built-in
  CommandPalette (`Ctrl+P`)
- **BINDINGS**: Modifier-combo shortcuts for all actions
- **on_mount**: Loads state, creates `SessionState`, starts services
- **Message handlers**: `on_state_file_changed` reloads state,
  `on_probe_complete` / `on_port_scan_complete` forward results to
  the active screen
- **Actions**: `action_add_route` (opens wizard), `action_delete_route`
  (confirm modal), `action_apply_changes` (persist draft), etc.

### `widgets.py`

| Widget | Purpose |
|--------|---------|
| `NavSidebar` | Vertical `ListView` with icon items. Posts `ScreenSelected` message on click. Shows proxy mode badge. |
| `StatusGrid` | `DataTable` — Name / Domain / Target / Status / Latency columns |
| `FlowDiagram` | ASCII traffic flow for the current proxy mode |
| `IntegrityPanel` | `DataTable` of file hashes + action buttons (Accept / Stop / Diff / Restore) |
| `DetailsPane` | `TabbedContent` with Flow, Verify, Logs, Config, Integrity tabs |

### `services.py`

All services take a single `app` argument and extract state from
`app.state`.

| Service | Trigger | Message posted |
|---------|---------|----------------|
| `StateWatcher` | watchdog `FileSystemEventHandler` on `~/.devhost/state.yml` (falls back to 2s mtime poll) | `StateFileChanged` |
| `ProbeService` | 30s interval, `@work(thread=True)` | `ProbeComplete(results)` |
| `LogTailService` | 1s interval | *(updates internal buffer, no message)* |
| `PortScanCache` | 30s TTL, on-demand via `ensure_scan()` | `PortScanComplete(ports)` |

### `cli_bridge.py`

Each bridge class exposes `async` static methods that run synchronous
CLI functions in a shared `ThreadPoolExecutor(max_workers=4)`:

```python
class RouterBridge:
    async def is_running() -> bool: ...
    async def start() -> str: ...
    async def stop() -> str: ...
    async def health_check() -> dict: ...
```

This keeps the Textual event loop unblocked.

### `screens/`

Each screen is a `Container` subclass living in its own file:

| Screen | File | Key widgets |
|--------|------|-------------|
| `RoutesScreen` | `routes.py` | StatusGrid + DetailsPane |
| `TunnelsScreen` | `tunnels.py` | DataTable + RadioSet for providers |
| `ProxyScreen` | `proxy.py` | Caddy lifecycle, external proxy, transfer, lockfile |
| `DiagnosticsScreen` | `diagnostics.py` | Router status, system info, integrity, bundle export |
| `SettingsScreen` | `settings.py` | LAN IP, OAuth, env sync, QR code |

Screens receive data through explicit method parameters (e.g.
`RoutesScreen.refresh_data(session, probe_results, ...)`), not by
reaching into `self.app` internals.

### `session.py` — SessionState

```python
state = SessionState(state_config)
state.set_route("api", "127.0.0.1:8000")   # draft
state.has_changes  # True
state.apply(state_config)                    # persist
state.reset()                                # discard
```

### `commands.py` — DevhostCommandProvider

Implements Textual's `Provider` protocol for the built-in
`CommandPalette`. Search is fuzzy-matched against 20+ commands:

- Navigate screens (Routes / Tunnels / Proxy / Diagnostics / Settings)
- Route CRUD (Add / Delete / Open / Copy URL / Copy Host / Copy Upstream)
- Operations (Refresh / Probe / Integrity / Apply / Export)
- Extras (QR code / Help / Emergency Reset)

### `wizard.py` — AddRouteWizard

Five-step `ModalScreen[bool]`:

0. **Ghost Port Detection** — auto-scans listening ports via `psutil`
1. **Identity & Target** — name + upstream with live validation
2. **Access Method** — Simple `localhost:PORT` vs Friendly URL
3. **Routing Mode** — Gateway / System / External (if Friendly URL)
4. **Review & Trust** — dry-run summary showing all files that will change

## Message Flow

```
User clicks sidebar "Tunnels"
  → NavSidebar posts ScreenSelected("tunnels")
  → app.on_nav_sidebar_screen_selected() → switcher.current = "tunnels"

watchdog detects state.yml change
  → StateWatcher posts StateFileChanged
  → app.on_state_file_changed() → reload state, refresh_data()

ProbeService completes a probe cycle
  → posts ProbeComplete(results)
  → app.on_probe_complete() → RoutesScreen.refresh_data(...)
```

## Testing

Tests live in `tests/test_tui.py` (43 tests). They cover:

- `SessionState` draft/apply/reset lifecycle
- `ProbeService` / `LogTailService` static helpers
- `PortScanCache` staleness and result API
- `NavSidebar` message structure
- `CommandPalette` command list
- Message types (`StateFileChanged`, `ProbeComplete`, `PortScanComplete`)
- Import correctness for all modules
- Keybinding modifier policy (no bare single-letter keys except `q`)
- Wizard apply logic
- Dead file removal assertions
- Integrity resolve/ignore
- DetailsPane verify and log display

Run:

```bash
python -m pytest tests/test_tui.py -v
python -m ruff check devhost_tui/
python -m ruff format --check devhost_tui/
```

## Deleted Legacy

The following files were removed during the v3 rewrite:

| File | Reason |
|------|--------|
| `state_manager.py` | Mixin — logic moved to `app.py` + `services.py` |
| `actions.py` | Mixin — `action_*` methods moved to `app.py` |
| `event_handlers.py` | Mixin — `on_*` handlers moved to `app.py` |
| `workers.py` | Mixin — `@work` methods moved to `services.py` |
| Legacy `AddRouteWizard` in `modals.py` | Replaced by `wizard.py` |
