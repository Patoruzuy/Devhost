"""
FastAPI application core with proxy endpoints.
"""

import asyncio
import inspect
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

from devhost_cli import __version__
from devhost_cli.router.cache import RouteCache
from devhost_cli.router.connection_pool import create_http_client, get_pool_metrics, request_with_retry
from devhost_cli.router.metrics import Metrics
from devhost_cli.router.utils import extract_subdomain, load_domain, parse_target

# Optional SSRF protection (security module is available in v3; keep router usable if missing)
try:
    from devhost_cli.router.security import validate_upstream_target
except Exception:  # pragma: no cover

    def validate_upstream_target(host: str, port: int) -> tuple[bool, str | None]:
        return (True, None)


# Optional WebSocket client support (for WebSocket proxying)
try:
    import websockets
    from websockets.exceptions import ConnectionClosed

    WEBSOCKETS_AVAILABLE = True
except ImportError:  # pragma: no cover
    WEBSOCKETS_AVAILABLE = False

# Configure logging with structured logging support (Phase 4 L-16)
LOG_REQUESTS = os.getenv("DEVHOST_LOG_REQUESTS", "").lower() in {"1", "true", "yes", "on"}

# Use structured logging setup if available
try:
    from devhost_cli.structured_logging import setup_logging

    setup_logging()
except ImportError:
    # Fallback to basic logging if structured logging not available
    LOG_LEVEL = os.getenv("DEVHOST_LOG_LEVEL", "INFO").upper()
    LOG_FILE = os.getenv("DEVHOST_LOG_FILE")
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


_WS_HEADERS_PARAM: str | None = None


def _ws_connect(url: str, extra_headers: list[tuple[str, str]] | None, subprotocols: list[str] | None):
    """Create a websockets client connection with version-compatible kwargs."""
    kwargs: dict = {}
    if subprotocols:
        kwargs["subprotocols"] = subprotocols

    if extra_headers:
        global _WS_HEADERS_PARAM
        if _WS_HEADERS_PARAM is None:
            params = set(inspect.signature(websockets.connect).parameters)  # type: ignore[name-defined]
            if "extra_headers" in params:
                _WS_HEADERS_PARAM = "extra_headers"
            elif "additional_headers" in params:
                _WS_HEADERS_PARAM = "additional_headers"
            else:  # Unknown signature; omit headers rather than crashing.
                _WS_HEADERS_PARAM = ""
        if _WS_HEADERS_PARAM:
            kwargs[_WS_HEADERS_PARAM] = extra_headers

    return websockets.connect(url, **kwargs)  # type: ignore[name-defined]


def create_app() -> FastAPI:
    """
    Create and configure the Devhost FastAPI application.

    Returns:
        Configured FastAPI app instance
    """
    # Validate configuration on startup
    try:
        from devhost_cli.config import validate_config

        is_valid, errors = validate_config()
        if not is_valid:
            logger.error("Config validation failed on startup:")
            for error in errors:
                logger.error("  - %s", error)
            logger.warning("Router will continue but some routes may not work correctly")
    except Exception as e:
        logger.warning("Config validation skipped due to error: %s", e)

    # Track in-flight requests for graceful shutdown (Phase 4 L-19)
    in_flight_requests = set()
    shutdown_event_obj = asyncio.Event()
    http_client = None

    # Optional security headers middleware (opt-in via DEVHOST_SECURITY_HEADERS=1)
    try:
        from devhost_cli.router.security_headers import SecurityHeadersMiddleware, is_security_headers_enabled
    except Exception:  # pragma: no cover - optional module
        SecurityHeadersMiddleware = None  # type: ignore[assignment]  # noqa: N806
        is_security_headers_enabled = None  # type: ignore[assignment]

    # Certificate status checks on startup (non-fatal)
    try:
        from devhost_cli.certificates import log_certificate_status, should_verify_certificates
    except Exception:  # pragma: no cover - optional module
        log_certificate_status = None
        should_verify_certificates = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal http_client
        if log_certificate_status:
            log_certificate_status()
        if should_verify_certificates and not should_verify_certificates():
            logger.warning("DEVHOST_VERIFY_CERTS is disabled; TLS certificate verification is off.")

        http_client = create_http_client()
        try:
            yield
        finally:
            logger.info("Shutdown initiated...")
            shutdown_event_obj.set()

            if in_flight_requests:
                logger.info(f"Waiting for {len(in_flight_requests)} in-flight requests...")
                timeout = 30.0  # 30 second timeout
                start_wait = time.time()

                while in_flight_requests and (time.time() - start_wait) < timeout:
                    await asyncio.sleep(0.1)

                if in_flight_requests:
                    logger.warning(
                        f"Forced shutdown: {len(in_flight_requests)} requests did not complete in {timeout}s"
                    )
                else:
                    logger.info("All in-flight requests completed")

            if http_client:
                await http_client.aclose()
            logger.info("Shutdown complete")

    app = FastAPI(lifespan=lifespan)

    if SecurityHeadersMiddleware and is_security_headers_enabled:
        try:
            headers_enabled = is_security_headers_enabled()
            app.add_middleware(SecurityHeadersMiddleware, enabled=headers_enabled)
            if headers_enabled:
                logger.info("Security headers middleware enabled")
        except Exception as e:
            logger.debug("Security headers middleware not available: %s", e)

    route_cache = RouteCache()
    metrics = Metrics()

    def _get_http_client() -> httpx.AsyncClient:
        nonlocal http_client
        if http_client is None:
            http_client = create_http_client()
        return http_client

    @app.middleware("http")
    async def request_metrics(request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]

        # Track in-flight requests (Phase 4 L-19)
        in_flight_requests.add(request_id)
        try:
            host_header = request.headers.get("host", "")
            subdomain = extract_subdomain(host_header, load_domain())
            start = time.time()
            response = await call_next(request)

            # Record metrics with latency (Phase 4 L-17)
            duration_ms = (time.time() - start) * 1000
            metrics.record(subdomain, response.status_code, latency_ms=duration_ms)

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            if LOG_REQUESTS:
                logger.info(
                    "[%s] %s %s -> %d (%dms)",
                    request_id,
                    request.method,
                    request.url.path or "/",
                    response.status_code,
                    int(duration_ms),
                )
            return response
        finally:
            # Remove from in-flight tracking
            in_flight_requests.discard(request_id)

    @app.get("/health")
    async def health():
        """
        Enhanced health endpoint for liveness and readiness checks (Phase 4 L-18).

        Returns:
        - status: ok or shutting_down
        - version: router version
        - uptime_seconds: uptime in seconds
        - routes_count: number of configured routes
        - in_flight_requests: current in-flight request count
        - connection_pool: connection pool health status
        - memory_mb: approximate memory usage in MB
        """
        routes = await route_cache.get_routes()
        pool_metrics = get_pool_metrics()

        # Get memory usage (optional, gracefully handle if not available)
        memory_mb = None
        try:
            import psutil

            process = psutil.Process()
            memory_mb = round(process.memory_info().rss / 1024 / 1024, 1)
        except Exception:
            pass  # psutil not available or failed

        response_data = {
            "status": "shutting_down" if shutdown_event_obj.is_set() else "ok",
            "version": __version__,
            "uptime_seconds": int(time.time() - metrics.start_time),
            "routes_count": len(routes),
            "in_flight_requests": len(in_flight_requests),
            "connection_pool": {
                "status": "healthy" if pool_metrics.get("success_rate", 0) > 0.9 else "degraded",
                "success_rate": pool_metrics.get("success_rate", 1.0),
            },
        }

        if memory_mb is not None:
            response_data["memory_mb"] = memory_mb

        return JSONResponse(response_data)

    @app.get("/metrics")
    async def metrics_endpoint():
        """Basic request metrics with connection pool stats and route cache stats."""
        data = metrics.snapshot()
        data["connection_pool"] = get_pool_metrics()
        data["route_cache"] = route_cache.get_metrics()  # Phase 4 L-15
        return JSONResponse(data)

    @app.get("/routes")
    async def routes_endpoint():
        """Return current routes with parsed targets."""
        routes_map = await route_cache.get_routes()
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
        routes = await route_cache.get_routes()
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

    @app.websocket("/{full_path:path}")
    async def websocket_proxy(websocket: WebSocket, full_path: str):
        """Proxy WebSocket connections to upstream servers."""
        if not WEBSOCKETS_AVAILABLE:
            await websocket.close(code=1011, reason="WebSocket proxying not available")
            return

        routes = await route_cache.get_routes()

        host_header = websocket.headers.get("host", "")
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

        request_id = str(uuid.uuid4())[:8]
        target_scheme, target_host, target_port = target

        # Security: SSRF protection - validate upstream target (before accepting the handshake)
        valid, error_msg = validate_upstream_target(target_host, target_port)
        if not valid:
            # Record SSRF block (Phase 4 L-17)
            metrics.record_ssrf_block(reason=error_msg or "unknown")
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
        if websocket.url.query:
            upstream_url = f"{upstream_url}?{websocket.url.query}"

        logger.info("[%s] WebSocket connection: %s.%s -> %s", request_id, subdomain, base_domain, upstream_url)

        await websocket.accept()

        # Track WebSocket connection (Phase 4 L-17)
        metrics.record_websocket_connected()

        try:
            skip_headers = {
                "host",
                "connection",
                "upgrade",
                "sec-websocket-key",
                "sec-websocket-version",
                "sec-websocket-extensions",
                "sec-websocket-protocol",
            }
            extra_headers: list[tuple[str, str]] = []
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

            async with _ws_connect(upstream_url, extra_headers, subprotocols) as upstream_ws:

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

                done, pending = await asyncio.wait(
                    [
                        asyncio.create_task(client_to_upstream()),
                        asyncio.create_task(upstream_to_client()),
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                )

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
        finally:
            # Track WebSocket disconnection (Phase 4 L-17)
            metrics.record_websocket_disconnected()

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
    async def wildcard_proxy(request: Request, full_path: str):
        routes = await route_cache.get_routes()

        host_header = request.headers.get("host", "")
        base_domain = load_domain()
        subdomain = extract_subdomain(host_header, base_domain)
        if not subdomain:
            request_id = str(uuid.uuid4())[:8]
            if host_header in {"127.0.0.1:7777", "localhost:7777", "127.0.0.1", "localhost", ""}:
                logger.info("[%s] Direct router access without Host header: %s", request_id, host_header)
                return JSONResponse(
                    {
                        "error": "Missing or invalid Host header",
                        "hint": "Use devhost open <name> or send Host header (e.g. curl -H 'Host: hello.localhost' http://127.0.0.1:7777/)",
                        "request_id": request_id,
                    },
                    status_code=400,
                )
            logger.warning("[%s] Invalid Host header: %s", request_id, host_header)
            return JSONResponse({"error": "Missing or invalid Host header", "request_id": request_id}, status_code=400)

        target_value = routes.get(subdomain)
        target = parse_target(target_value)
        if not target:
            request_id = str(uuid.uuid4())[:8]
            logger.info("[%s] No route found for %s.%s", request_id, subdomain, base_domain)
            return JSONResponse(
                {"error": f"No route found for {subdomain}.{base_domain}", "request_id": request_id}, status_code=404
            )
        target_scheme, target_host, target_port = target

        # Security: SSRF protection - validate upstream target
        valid, error_msg = validate_upstream_target(target_host, target_port)
        if not valid:
            request_id = str(uuid.uuid4())[:8]
            # Record SSRF block (Phase 4 L-17)
            metrics.record_ssrf_block(reason=error_msg or "unknown")
            logger.error(
                "[%s] SSRF protection blocked request to %s:%d - %s",
                request_id,
                target_host,
                target_port,
                error_msg,
            )
            return JSONResponse(
                {"error": f"Security policy blocked this request: {error_msg}", "request_id": request_id},
                status_code=403,
            )

        # build upstream URL and preserve query string
        url = f"{target_scheme}://{target_host}:{target_port}{request.url.path}"
        if request.url.query:
            url = url + "?" + request.url.query

        headers = dict(request.headers)
        # remove host header so upstream sees correct host
        headers.pop("host", None)

        try:
            proxy_resp = await request_with_retry(
                _get_http_client(),
                method=request.method,
                url=url,
                headers=headers,
                content=await request.body(),
            )
        except httpx.RequestError as exc:
            request_id = str(uuid.uuid4())[:8]
            logger.warning(
                "[%s] Upstream request failed for %s.%s -> %s: %s", request_id, subdomain, base_domain, url, exc
            )
            return JSONResponse({"error": f"Upstream request failed: {exc}", "request_id": request_id}, status_code=502)

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
        }
        resp_headers = {k: v for k, v in proxy_resp.headers.items() if k.lower() not in excluded}

        return Response(content=proxy_resp.content, status_code=proxy_resp.status_code, headers=resp_headers)

    return app
