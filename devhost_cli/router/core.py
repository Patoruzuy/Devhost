"""
FastAPI application core with proxy endpoints.
"""

import asyncio
import logging
import os
import time
import uuid

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from devhost_cli import __version__
from devhost_cli.router.cache import RouteCache
from devhost_cli.router.metrics import Metrics
from devhost_cli.router.utils import extract_subdomain, load_domain, parse_target

# Configure logging
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


def create_app() -> FastAPI:
    """
    Create and configure the Devhost FastAPI application.

    Returns:
        Configured FastAPI app instance
    """
    app = FastAPI()
    route_cache = RouteCache()
    metrics = Metrics()

    @app.middleware("http")
    async def request_metrics(request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]

        host_header = request.headers.get("host", "")
        subdomain = extract_subdomain(host_header, load_domain())
        start = time.time()
        response = await call_next(request)
        metrics.record(subdomain, response.status_code)

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
        routes = await route_cache.get_routes()
        return JSONResponse(
            {
                "status": "ok",
                "version": __version__,
                "routes_count": len(routes),
                "uptime_seconds": int(time.time() - metrics.start_time),
            }
        )

    @app.get("/metrics")
    async def metrics_endpoint():
        """Basic request metrics."""
        return JSONResponse(metrics.snapshot())

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

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
    async def wildcard_proxy(request: Request, full_path: str):
        routes = await route_cache.get_routes()

        host_header = request.headers.get("host", "")
        base_domain = load_domain()
        subdomain = extract_subdomain(host_header, base_domain)
        if not subdomain:
            request_id = str(uuid.uuid4())[:8]
            if host_header in {"127.0.0.1:5555", "localhost:5555", "127.0.0.1", "localhost", ""}:
                logger.info("[%s] Direct router access without Host header: %s", request_id, host_header)
                return JSONResponse(
                    {
                        "error": "Missing or invalid Host header",
                        "hint": "Use devhost open <name> or send Host header (e.g. curl -H 'Host: hello.localhost' http://127.0.0.1:5555/)",
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

        # build upstream URL and preserve query string
        url = f"{target_scheme}://{target_host}:{target_port}{request.url.path}"
        if request.url.query:
            url = url + "?" + request.url.query

        async with httpx.AsyncClient() as client:
            headers = dict(request.headers)
            # remove host header so upstream sees correct host
            headers.pop("host", None)
            try:
                proxy_resp = await client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    content=await request.body(),
                    timeout=30.0,
                )
            except httpx.RequestError as exc:
                request_id = str(uuid.uuid4())[:8]
                logger.warning(
                    "[%s] Upstream request failed for %s.%s -> %s: %s", request_id, subdomain, base_domain, url, exc
                )
                return JSONResponse(
                    {"error": f"Upstream request failed: {exc}", "request_id": request_id}, status_code=502
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
        }
        resp_headers = {k: v for k, v in proxy_resp.headers.items() if k.lower() not in excluded}

        return Response(content=proxy_resp.content, status_code=proxy_resp.status_code, headers=resp_headers)

    return app
