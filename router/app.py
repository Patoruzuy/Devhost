import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import httpx
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

try:
    import websockets
    from websockets.exceptions import ConnectionClosed

    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

# Security imports
try:
    from devhost_cli.router.security import validate_upstream_target
except ImportError:
    # Fallback if security module not available
    def validate_upstream_target(host: str, port: int) -> tuple[bool, str | None]:
        return (True, None)


# Global client
http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    # Disable timeouts for the client itself, control per-request or keep defaults
    # Limits might be needed for high concurrency
    http_client = httpx.AsyncClient(limits=httpx.Limits(max_keepalive_connections=20, max_connections=100))
    yield
    await http_client.aclose()


app = FastAPI(lifespan=lifespan)

LOG_LEVEL = os.getenv("DEVHOST_LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("DEVHOST_LOG_FILE")
LOG_REQUESTS = os.getenv("DEVHOST_LOG_REQUESTS", "").lower() in {"1", "true", "yes", "on"}
handlers = [logging.StreamHandler()]
if LOG_FILE:
    try:
        handlers.append(logging.FileHandler(LOG_FILE))
    except Exception:
        pass
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    handlers=handlers,
    force=True,
)
logger = logging.getLogger("devhost.router")
START_TIME = time.time()

# Configurable timeout (default 60s for debugging sessions)
DEFAULT_TIMEOUT = int(os.getenv("DEVHOST_TIMEOUT", "60"))

# Retry configuration for transient connection errors
RETRY_ATTEMPTS = int(os.getenv("DEVHOST_RETRY_ATTEMPTS", "3"))
RETRY_DELAY_MS = int(os.getenv("DEVHOST_RETRY_DELAY_MS", "500"))

# HTML error page template with auto-refresh
HTML_ERROR_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Devhost - {status_code}</title>
    <meta http-equiv="refresh" content="3">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               display: flex; justify-content: center; align-items: center; height: 100vh;
               margin: 0; background: #1a1a2e; color: #eee; }}
        .container {{ text-align: center; padding: 2rem; }}
        h1 {{ font-size: 4rem; margin: 0; color: #e94560; }}
        p {{ color: #aaa; margin: 1rem 0; }}
        .hint {{ background: #16213e; padding: 1rem; border-radius: 8px; margin-top: 1rem; }}
        code {{ color: #0f9b0f; }}
        .spinner {{ display: inline-block; width: 20px; height: 20px; border: 2px solid #444;
                   border-top-color: #e94560; border-radius: 50%; animation: spin 1s linear infinite; }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{status_code}</h1>
        <p>{message}</p>
        <div class="hint">
            <span class="spinner"></span>
            <span>Auto-refreshing in 3 seconds...</span>
        </div>
        <p style="font-size: 0.8rem; color: #666;">Request ID: {request_id}</p>
    </div>
</body>
</html>
"""


class Metrics:
    def __init__(self) -> None:
        self.requests_total = 0
        self.requests_by_status: dict[int, int] = {}
        self.requests_by_subdomain: dict[str, dict[str, int]] = {}

    def record(self, subdomain: str | None, status_code: int) -> None:
        self.requests_total += 1
        self.requests_by_status[status_code] = self.requests_by_status.get(status_code, 0) + 1
        if subdomain:
            bucket = self.requests_by_subdomain.setdefault(subdomain, {"count": 0, "errors": 0})
            bucket["count"] += 1
            if status_code >= 400:
                bucket["errors"] += 1

    def snapshot(self) -> dict[str, object]:
        return {
            "uptime_seconds": int(time.time() - START_TIME),
            "requests_total": self.requests_total,
            "requests_by_status": self.requests_by_status,
            "requests_by_subdomain": self.requests_by_subdomain,
        }


METRICS = Metrics()


def load_domain() -> str:
    env_domain = os.getenv("DEVHOST_DOMAIN")
    if env_domain:
        return env_domain.strip().lower()
    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / ".devhost" / "domain",
        Path.home() / ".devhost" / "domain",
        here.parent.parent / ".devhost" / "domain",
        here.parent / ".devhost" / "domain",
    ]
    for path in candidates:
        try:
            if path.is_file():
                value = path.read_text().strip().lower()
                if value:
                    return value
        except Exception:
            continue
    return "localhost"


def extract_subdomain(host_header: str | None, base_domain: str | None = None) -> str | None:
    if not host_header:
        return None
    base_domain = (base_domain or load_domain()).strip(".").lower()
    if not base_domain:
        return None
    # strip port if present
    host_only = host_header.split(":")[0].strip().lower()
    suffix = f".{base_domain}"
    if not host_only.endswith(suffix):
        return None
    sub = host_only[: -len(suffix)]
    if not sub:
        return None
    return sub


def _config_candidates() -> list[Path]:
    candidates = []
    env_path = os.getenv("DEVHOST_CONFIG")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path.home() / ".devhost" / "devhost.json")
    candidates.append(Path.cwd() / "devhost.json")
    here = Path(__file__).resolve()
    # repo root (../devhost.json) and legacy router-local file
    candidates.append(here.parent.parent / "devhost.json")
    candidates.append(here.parent / "devhost.json")

    # de-duplicate while preserving order
    seen = set()
    unique = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def _load_routes_from_path(path: Path) -> dict[str, int] | None:
    try:
        content = path.read_text()
        if not content.strip():
            return {}
        data = json.loads(content)
        if isinstance(data, dict):
            return {str(k).lower(): v for k, v in data.items()}
    except Exception as exc:
        logger.warning("Failed to load config from %s: %s", path, exc)
        return None
    return {}


def _select_config_path() -> Path | None:
    for path in _config_candidates():
        try:
            if path.is_file():
                return path
        except Exception:
            continue
    return None


class RouteCache:
    def __init__(self) -> None:
        self._routes: dict[str, int] = {}
        self._last_mtime: float = 0.0
        self._last_path: Path | None = None
        self._lock = asyncio.Lock()

    async def get_routes(self) -> dict[str, int]:
        path = _select_config_path()
        if not path:
            if self._routes:
                logger.info("Config file not found; clearing routes cache.")
                self._routes = {}
                self._last_mtime = 0.0
                self._last_path = None
            return {}
        try:
            mtime = path.stat().st_mtime
        except Exception as exc:
            logger.warning("Failed to stat config file %s: %s", path, exc)
            return self._routes

        if self._last_path != path or mtime > self._last_mtime:
            async with self._lock:
                try:
                    mtime = path.stat().st_mtime
                except Exception as exc:
                    logger.warning("Failed to stat config file %s: %s", path, exc)
                    return self._routes
                if self._last_path != path or mtime > self._last_mtime:
                    loaded = _load_routes_from_path(path)
                    if loaded is None:
                        logger.warning("Keeping previous routes due to config parse error.")
                    else:
                        self._routes = loaded
                        logger.info("Loaded %d routes from %s", len(self._routes), path)
                    self._last_mtime = mtime
                    self._last_path = path
        return self._routes


ROUTE_CACHE = RouteCache()


def wants_html(request: Request) -> bool:
    """Check if client prefers HTML response (browser vs API client)."""
    accept = request.headers.get("accept", "")
    # Browsers typically send text/html first
    return "text/html" in accept.split(",")[0] if accept else False


def error_response(
    request: Request,
    status_code: int,
    message: str,
    request_id: str,
    hint: str | None = None,
) -> JSONResponse | HTMLResponse:
    """Return smart error response based on Accept header.

    - HTML clients (browsers) get a friendly page with auto-refresh
    - API clients get JSON
    """
    if wants_html(request):
        html = HTML_ERROR_TEMPLATE.format(
            status_code=status_code,
            message=message,
            request_id=request_id,
        )
        return HTMLResponse(content=html, status_code=status_code)

    error_data = {"error": message, "request_id": request_id}
    if hint:
        error_data["hint"] = hint
    return JSONResponse(error_data, status_code=status_code)


def parse_target(value) -> tuple[str, int, str] | None:
    if value is None:
        return None
    if isinstance(value, int):
        if value > 0:
            return ("http", "127.0.0.1", value)
        return None
    if isinstance(value, str):
        if value.startswith("http://") or value.startswith("https://"):
            parsed = urlparse(value)
            if parsed.hostname and parsed.port:
                return (parsed.scheme, parsed.hostname, parsed.port)
            return None
        if ":" in value:
            host, port = value.rsplit(":", 1)
            if host and port.isdigit():
                return ("http", host, int(port))
            return None
        if value.isdigit():
            port = int(value)
            if port > 0:
                return ("http", "127.0.0.1", port)
            return None
    return None


@app.middleware("http")
async def request_metrics(request: Request, call_next):
    # Generate unique request ID
    request_id = str(uuid.uuid4())[:8]

    host_header = request.headers.get("host", "")
    subdomain = extract_subdomain(host_header, load_domain())
    start = time.time()
    response = await call_next(request)
    METRICS.record(subdomain, response.status_code)

    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id

    if LOG_REQUESTS:
        duration_ms = int((time.time() - start) * 1000)
        logger.info(
            "[%s] %s %s -> %d (%dms)",
            request_id,
            request.method,
            request.url.path or "/",
            response.status_code,
            duration_ms,
        )
    return response


@app.get("/health")
async def health():
    """Lightweight health endpoint for liveness checks."""
    routes = await ROUTE_CACHE.get_routes()
    return JSONResponse(
        {
            "status": "ok",
            "version": "v1.0.0",
            "routes_count": len(routes),
            "uptime_seconds": int(time.time() - START_TIME),
        }
    )


@app.get("/metrics")
async def metrics():
    """Basic request metrics."""
    return JSONResponse(METRICS.snapshot())


@app.get("/routes")
async def routes():
    """Return current routes with parsed targets."""
    routes_map = await ROUTE_CACHE.get_routes()
    domain = load_domain()
    output = {}
    for name, target_value in routes_map.items():
        target = parse_target(target_value)
        if not target:
            output[name] = {"target": target_value, "error": "invalid target"}
            continue
        scheme, host, port = target
        output[name] = {
            "url": f"{scheme}://{name}.{domain}",
            "target": f"{scheme}://{host}:{port}",
            "raw": target_value,
        }
    return JSONResponse({"domain": domain, "routes": output})


async def _check_tcp(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        conn = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        reader, writer = conn
        writer.close()
        if hasattr(writer, "wait_closed"):
            await writer.wait_closed()
        return True
    except Exception:
        return False


@app.get("/mappings")
async def mappings():
    """Return current mappings with basic TCP health checks."""
    routes = await ROUTE_CACHE.get_routes()
    results = {}
    checks = []
    names = []
    for name, target_value in routes.items():
        target = parse_target(target_value)
        if not target:
            results[name] = {"target": target_value, "healthy": False, "error": "invalid target"}
            continue
        scheme, host, port = target
        names.append(name)
        checks.append(_check_tcp(host, port))
        results[name] = {"target": f"{scheme}://{host}:{port}"}
    if checks:
        statuses = await asyncio.gather(*checks, return_exceptions=True)
        for idx, status in enumerate(statuses):
            healthy = bool(status is True)
            results[names[idx]]["healthy"] = healthy
    return JSONResponse({"domain": load_domain(), "mappings": results})


# WebSocket proxy endpoint
@app.websocket("/{full_path:path}")
async def websocket_proxy(websocket: WebSocket, full_path: str):
    """Proxy WebSocket connections to upstream servers."""
    if not WEBSOCKETS_AVAILABLE:
        await websocket.close(code=1011, reason="WebSocket proxying not available")
        return

    routes = await ROUTE_CACHE.get_routes()

    request_id = str(uuid.uuid4())[:8]

    # Extract subdomain from headers
    host_header = None
    for header in websocket.headers.raw:
        if header[0].lower() == b"host":
            host_header = header[1].decode("utf-8")
            break

    base_domain = load_domain()
    subdomain = extract_subdomain(host_header, base_domain)

    if not subdomain:
        await websocket.close(code=1008, reason="Missing or invalid Host header")
        return

    target_value = routes.get(subdomain)
    target = parse_target(target_value)
    if not target:
        await websocket.close(code=1008, reason=f"No route found for {subdomain}.{base_domain}")
        return

    target_scheme, target_host, target_port = target

    # Security: SSRF protection - validate upstream target (before accepting the handshake)
    valid, error_msg = validate_upstream_target(target_host, target_port)
    if not valid:
        logger.error(
            "[%s] SSRF protection blocked WebSocket to %s:%d - %s",
            request_id,
            target_host,
            target_port,
            error_msg,
        )
        try:
            await websocket.close(code=1008, reason="Security policy blocked this upstream (SSRF protection)")
        except Exception:
            pass
        return

    ws_scheme = "wss" if target_scheme == "https" else "ws"
    upstream_url = f"{ws_scheme}://{target_host}:{target_port}/{full_path}"

    # Add query string if present
    if websocket.url.query:
        upstream_url = f"{upstream_url}?{websocket.url.query}"

    logger.info("[%s] WebSocket connection: %s.%s -> %s", request_id, subdomain, base_domain, upstream_url)

    await websocket.accept()

    try:
        # Forward client headers and subprotocols to upstream where applicable
        skip_headers = {
            "host",
            "connection",
            "upgrade",
            "sec-websocket-key",
            "sec-websocket-version",
            "sec-websocket-extensions",
            "sec-websocket-protocol",
        }
        extra_headers = []
        for name_bytes, value_bytes in websocket.headers.raw:
            name = name_bytes.decode("latin-1")
            lname = name.lower()
            if lname in skip_headers:
                continue
            extra_headers.append((name, value_bytes.decode("latin-1")))

        protocol_header = websocket.headers.get("sec-websocket-protocol")
        subprotocols = None
        if protocol_header:
            subprotocols = [p.strip() for p in protocol_header.split(",") if p.strip()]

        async with websockets.connect(
            upstream_url,
            extra_headers=extra_headers,
            subprotocols=subprotocols,
        ) as upstream_ws:
            # Create tasks for bidirectional communication
            async def client_to_upstream():
                try:
                    while True:
                        data = await websocket.receive()
                        if data.get("type") == "websocket.disconnect":
                            break
                        if "text" in data:
                            await upstream_ws.send(data["text"])
                        elif "bytes" in data:
                            await upstream_ws.send(data["bytes"])
                except WebSocketDisconnect:
                    pass

            async def upstream_to_client():
                try:
                    async for message in upstream_ws:
                        if isinstance(message, str):
                            await websocket.send_text(message)
                        else:
                            await websocket.send_bytes(message)
                except ConnectionClosed:
                    pass

            # Run both directions concurrently
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(client_to_upstream()),
                    asyncio.create_task(upstream_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    except Exception as exc:
        logger.warning("[%s] WebSocket proxy error: %s", request_id, exc)
        try:
            await websocket.close(code=1011, reason="Upstream connection failed")
        except Exception:
            pass


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def wildcard_proxy(request: Request, full_path: str):
    routes = await ROUTE_CACHE.get_routes()
    request_id = str(uuid.uuid4())[:8]

    host_header = request.headers.get("host", "")
    base_domain = load_domain()
    subdomain = extract_subdomain(host_header, base_domain)
    if not subdomain:
        if host_header in {"127.0.0.1:7777", "localhost:7777", "127.0.0.1", "localhost", ""}:
            logger.info("[%s] Direct router access without Host header: %s", request_id, host_header)
            return error_response(
                request,
                400,
                "Missing or invalid Host header",
                request_id,
                hint="Use devhost open <name> or send Host header (e.g. curl -H 'Host: hello.localhost' http://127.0.0.1:7777/)",
            )
        logger.warning("[%s] Invalid Host header: %s", request_id, host_header)
        return error_response(request, 400, "Missing or invalid Host header", request_id)

    # Look up target route
    target_value = routes.get(subdomain)
    target = parse_target(target_value)
    if not target:
        logger.warning("[%s] No route found for %s.%s", request_id, subdomain, base_domain)
        return error_response(request, 404, f"No route found for {subdomain}.{base_domain}", request_id)

    # Build upstream URL
    target_scheme, target_host, target_port = target

    # Security: SSRF protection - validate upstream target
    valid, error_msg = validate_upstream_target(target_host, target_port)
    if not valid:
        logger.error(
            "[%s] SSRF protection blocked request to %s:%d - %s", request_id, target_host, target_port, error_msg
        )
        METRICS.record(subdomain, 403)

        # Provide migration hint for legitimate local development
        hint = None
        if "private IP" in (error_msg or ""):
            hint = "This appears to be a local development app. Set DEVHOST_ALLOW_PRIVATE_NETWORKS=1 to enable."

        return error_response(
            request,
            403,
            f"Security policy blocked this request: {error_msg}",
            request_id,
            hint=hint,
        )

    url = f"{target_scheme}://{target_host}:{target_port}/{full_path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    # Prepare headers with standard proxy headers
    headers = dict(request.headers)
    original_host = headers.pop("host", host_header)

    # Add standard proxy headers (X-Forwarded-*)
    client_ip = request.client.host if request.client else "127.0.0.1"
    headers["X-Forwarded-For"] = headers.get("x-forwarded-for", client_ip)
    headers["X-Forwarded-Host"] = original_host
    existing_proto = headers.get("x-forwarded-proto") or headers.get("X-Forwarded-Proto")
    forwarded_proto = request.url.scheme or "http"
    # Only trust X-Forwarded-Proto from a local, trusted proxy
    if client_ip in {"127.0.0.1", "::1"} and existing_proto:
        forwarded_proto = existing_proto.split(",")[0].strip().lower() or forwarded_proto
    headers.pop("x-forwarded-proto", None)
    headers.pop("X-Forwarded-Proto", None)
    headers["X-Forwarded-Proto"] = forwarded_proto
    headers["X-Real-IP"] = client_ip

    # Use globally shared client
    global http_client
    # Fallback if lifecycle didn't run (e.g. some tests)
    if http_client is None:
        http_client = httpx.AsyncClient()

    # Stream request body (cache for retries)
    body_chunks: list[bytes] = []
    async for chunk in request.stream():
        body_chunks.append(chunk)
    body_content = b"".join(body_chunks)

    # Retry loop for transient connection errors (server restarting)
    last_error: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            req = http_client.build_request(
                method=request.method,
                url=url,
                headers=headers,
                content=body_content,
                timeout=float(DEFAULT_TIMEOUT),
            )
            upstream_resp = await http_client.send(req, stream=True)
            break  # Success - exit retry loop
        except httpx.ConnectError as exc:
            # Connection refused - server might be restarting
            last_error = exc
            if attempt < RETRY_ATTEMPTS - 1:
                logger.debug(
                    "[%s] Connection refused (attempt %d/%d), retrying in %dms...",
                    request_id,
                    attempt + 1,
                    RETRY_ATTEMPTS,
                    RETRY_DELAY_MS,
                )
                await asyncio.sleep(RETRY_DELAY_MS / 1000.0)
            continue
        except httpx.RequestError as exc:
            # Other request errors - don't retry
            logger.warning(
                "[%s] Upstream request failed for %s.%s -> %s: %s", request_id, subdomain, base_domain, url, exc
            )
            return error_response(request, 502, f"Upstream server unavailable: {type(exc).__name__}", request_id)
    else:
        # All retries exhausted
        logger.warning(
            "[%s] Upstream connection failed after %d attempts for %s.%s -> %s: %s",
            request_id,
            RETRY_ATTEMPTS,
            subdomain,
            base_domain,
            url,
            last_error,
        )
        return error_response(
            request, 502, f"Upstream server not responding (tried {RETRY_ATTEMPTS} times)", request_id
        )

    # Filter hop-by-hop headers
    excluded = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-encoding",  # Let upstream handle encoding, or httpx might decompress
        "content-length",  # Length changes if we process it
    }
    resp_headers = {k: v for k, v in upstream_resp.headers.items() if k.lower() not in excluded}

    # Stream response back to client
    return StreamingResponse(
        upstream_resp.aiter_bytes(),
        status_code=upstream_resp.status_code,
        headers=resp_headers,
        background=BackgroundTask(upstream_resp.aclose),
    )


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=7777, reload=True)
