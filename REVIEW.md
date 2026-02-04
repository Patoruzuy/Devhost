# Engineering Review of Devhost v3.0

As requested, I have performed a senior-level review of the Devhost repository. I have identified critical issues affecting stability and performance and have already applied fixes for the most urgent ones. Below is the full report including applied fixes and future recommendations.

## 1. Critical Fixes Applied

### 🚨 Port Inconsistency (Fixed)
- **Issue:** The router runs on port `7777`, but the process manager (`router_manager.py`) was checking port `5555` for health/liveness.
- **Impact:** `devhost` commands would fail to detect if the router was running, potentially spawning multiple instances or failing to start.
- **Fix:** Updated `router_manager.py` to check `http://127.0.0.1:7777/health`.

### 🚀 Connection Management (Fixed)
- **Issue:** The router was creating a new `httpx.AsyncClient` for **every request**.
- **Impact:** Massive overhead from TCP/SSL handshakes. High latency and port exhaustion under load.
- **Fix:** Refactored `router/app.py` to use a global `httpx.AsyncClient` managed via FastAPI's lifespan events.

### 🌊 Memory & Streaming (Fixed)
- **Issue:** The proxy was loading the **entire** request and response bodies into memory (`await request.body()`).
- **Impact:** Uploading/downloading large files would crash the router (OOM). High concurrency would spike memory usage.
- **Fix:** Implemented full full-duplex streaming. The router now streams request chunks to the upstream and streams response chunks back to the client immediately.

## 2. Architecture Review

### Strengths
- **Simplicity:** The design is clean and easy to understand.
- **Extensibility:** The CLI structure with `click` and modular `frameworks/` is excellent.
- **Dev Experience:** features like `devhost open`, local domains, and TUI integration are great for developer productivity.

### Weaknesses
- **Python Proxy Loop:** Using Python for the data plane (the actual proxying) introduces the GIL bottleneck. While `asyncio` helps with I/O, heavy throughput might still be limited compared to Go (Caddy/Traefik) or Rust. However, for a *local development* tool, this is acceptable.
- **Hardcoded Logic:** Some logic (like config paths and ports) was scattered.

## 3. High-Impact Recommendations

### 🛡️ Resilience & Stability
- **Circuit Breakers:** If an upstream service is down, the router currently just fails. Implementing a simple "circuit breaker" or "health check" before trying to forward every request would improve responsiveness.
- **Retries:** Add configurable retries for idempotent methods (GET/HEAD) to handle transient upstream flakes.

### 🔍 Observability
- **Structured Logging:** Currently logging to stdout/file in text format. For "System Mode", switching to JSON logging would make it easier to ingest into local observability tools.
- **Prometheus Metrics:** The `/metrics` endpoint is custom. Using the standard Prometheus text format would allow users to plug in Grafana/Prometheus for local monitoring.

### 🔒 Security
- **Host Header Validation:** I noticed `wildcard_proxy` strips the `Host` header. While often necessary, some frameworks (Django/Flask) need the original Host header to generate correct absolute URLs.
  - **Suggestion:** Add a configuration option enabled by default to send `X-Forwarded-Host: <original_host>`.

### ⚡ Performance
- **Connection Limits:** I added a default limit of 100 connections to the global client. This should be exposed in configuration (e.g., `DEVHOST_MAX_CONNS`) to allow tuning for heavier workloads.

## 4. Code Quality Notes
- **Type Hinting:** Excellent coverage.
- **Project Structure:** Logical separation of CLI, Router, and State.
- **Dependencies:** `httpx` and `fastapi` are solid choices.

## Summary
The codebase is healthy. The critical fixes I applied (Streaming & Connection Pooling) upgrade the router from "toy" status to a robust tool capable of handling real developer workloads (large uploads, many requests).
