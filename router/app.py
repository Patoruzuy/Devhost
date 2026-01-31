from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
import httpx
import json
import os
import logging
import asyncio
import time
from pathlib import Path
import uvicorn
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse

app = FastAPI()

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


class Metrics:
    def __init__(self) -> None:
        self.requests_total = 0
        self.requests_by_status: Dict[int, int] = {}
        self.requests_by_subdomain: Dict[str, Dict[str, int]] = {}

    def record(self, subdomain: Optional[str], status_code: int) -> None:
        self.requests_total += 1
        self.requests_by_status[status_code] = self.requests_by_status.get(status_code, 0) + 1
        if subdomain:
            bucket = self.requests_by_subdomain.setdefault(subdomain, {"count": 0, "errors": 0})
            bucket["count"] += 1
            if status_code >= 400:
                bucket["errors"] += 1

    def snapshot(self) -> Dict[str, object]:
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


def extract_subdomain(host_header: Optional[str], base_domain: Optional[str] = None) -> Optional[str]:
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


def _load_routes_from_path(path: Path) -> Optional[Dict[str, int]]:
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


def _select_config_path() -> Optional[Path]:
    for path in _config_candidates():
        try:
            if path.is_file():
                return path
        except Exception:
            continue
    return None


class RouteCache:
    def __init__(self) -> None:
        self._routes: Dict[str, int] = {}
        self._last_mtime: float = 0.0
        self._last_path: Optional[Path] = None
        self._lock = asyncio.Lock()

    async def get_routes(self) -> Dict[str, int]:
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


def parse_target(value) -> Optional[Tuple[str, int, str]]:
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
    host_header = request.headers.get("host", "")
    subdomain = extract_subdomain(host_header, load_domain())
    start = time.time()
    response = await call_next(request)
    METRICS.record(subdomain, response.status_code)
    if LOG_REQUESTS:
        duration_ms = int((time.time() - start) * 1000)
        logger.info(
            "%s %s -> %d (%dms)",
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


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def wildcard_proxy(request: Request, full_path: str):
    routes = await ROUTE_CACHE.get_routes()

    host_header = request.headers.get("host", "")
    base_domain = load_domain()
    subdomain = extract_subdomain(host_header, base_domain)
    if not subdomain:
        if host_header in {"127.0.0.1:5555", "localhost:5555", "127.0.0.1", "localhost", ""}:
            logger.info("Direct router access without Host header: %s", host_header)
            return JSONResponse(
                {
                    "error": "Missing or invalid Host header",
                    "hint": "Use devhost open <name> or send Host header (e.g. curl -H 'Host: hello.localhost' http://127.0.0.1:5555/)",
                },
                status_code=400,
            )
        logger.warning("Invalid Host header: %s", host_header)
        return JSONResponse({"error": "Missing or invalid Host header"}, status_code=400)

    target_value = routes.get(subdomain)
    target = parse_target(target_value)
    if not target:
        logger.info("No route found for %s.%s", subdomain, base_domain)
        return JSONResponse({"error": f"No route found for {subdomain}.{base_domain}"}, status_code=404)
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
            logger.warning("Upstream request failed for %s.%s -> %s: %s", subdomain, base_domain, url, exc)
            return JSONResponse({"error": f"Upstream request failed: {exc}"}, status_code=502)

    # Filter hop-by-hop headers
    excluded = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"}
    resp_headers = {k: v for k, v in proxy_resp.headers.items() if k.lower() not in excluded}

    return Response(content=proxy_resp.content, status_code=proxy_resp.status_code, headers=resp_headers)


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5555, reload=True)
