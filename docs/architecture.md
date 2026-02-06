# Architecture Overview

Devhost is built on a modular architecture that separates the data plane (proxying) from the control plane (management).

## Design Principles

### 1. Minimal Intrusion
Devhost avoids modifying system settings unless explicitly requested. The default "Gateway" mode operates entirely in userspace without administrative privileges.

### 2. Transparent State
All configuration is file-based and stored in human-readable YAML and JSON in `~/.devhost/`. There are no hidden databases.

### 3. Ownership Model
Devhost only "owns" the artifacts it creates. It treats user-owned configurations (like an existing `nginx.conf`) as sacred and only modifies them using clearly marked, reversible blocks.

## Components

### CLI (`devhost`)
The command-line interface is the primary control point. It manages:
- **Routes**: Stored in `~/.devhost/devhost.json`.
- **Global State**: Stored in `~/.devhost/state.yml` (mode, integrity, proxy metadata).
- **Diagnostics**: Health checks, bundle exports, and "doctor" fixes.

### Gateway Router (Mode 1)
A high-performance FastAPI/Uvicorn application that handles the actual proxying.
- **Traffic Routing**: Uses the `Host` header to dispatch requests to upstream targets.
- **WebSocket Support**: Automatically detects `Upgrade: websocket` headers and establishes bidirectional proxying.
- **Full Streaming**: Request and response bodies are streamed to minimize memory usage, supporting large file transfers.
- **Connection Pooling**: Uses a global `httpx` client to reuse TCP connections.

### Lifecycle Manager (Mode 2)
Manages a system-wide Caddy process.
- **Mode-2 Caddyfile**: Auto-generated in `~/.devhost/proxy/caddy/Caddyfile`.
- **Process Management**: Monitors the Caddy PID and handles graceful restarts.
- **Port Conflict Detection**: Proactively identifies processes using ports 80/443 and offers tailored resolution advice.

### External Proxy Integration (Mode 3)
Generates configuration snippets for Nginx, Traefik, and Caddy.
- **Attach/Detach**: Safely injects routes into existing server configurations.
- **Integrity Hashing**: Uses SHA-256 hashes to detect manual modifications ("drift") in generated files.

## Data Flow

1. **Request**: Browser requests `http://api.localhost:7777`.
2. **Detection**: Router receives the request and inspects the `Host` header (`api.localhost:7777`).
3. **Resolution**: Router looks up "api" in the mapping table.
4. **Proxy**: Router forwards the request to the upstream (e.g., `127.0.0.1:8000`).
5. **Streaming**: Data flows back and forth between the client and upstream via full-duplex streams.

## Security Model

Devhost implements a defense-in-depth approach:
- **SSRF Shield**: Built-in blocklists for 169.254.169.254 and private IP ranges.
- **Hostname Sanitization**: Strict RFC 1123 validation for all incoming hostnames.
- **Privilege Separation**: Only the minimum necessary commands (like port 80 binding) request elevation.
