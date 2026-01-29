from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
import httpx
import json
import os
from pathlib import Path
import uvicorn
from typing import Optional, Dict

app = FastAPI()


def extract_subdomain(host_header: Optional[str]) -> Optional[str]:
    if not host_header:
        return None
    # strip port if present
    host_only = host_header.split(":")[0].strip().lower()
    if not host_only.endswith(".localhost"):
        return None
    parts = host_only.split(".")
    if len(parts) < 2:
        return None
    # return everything before ".localhost"
    return ".".join(parts[:-1])


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


def load_routes() -> Dict[str, int]:
    for path in _config_candidates():
        try:
            if path.is_file():
                with path.open() as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return {str(k).lower(): v for k, v in data.items()}
        except Exception:
            continue
    return {}


@app.get("/health")
async def health():
    """Lightweight health endpoint for liveness checks."""
    return JSONResponse({"status": "ok", "version": "v1.0.0"})


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def wildcard_proxy(request: Request, full_path: str):
    # Load routes on each request so CLI updates take effect immediately
    routes = load_routes()

    host_header = request.headers.get("host", "")
    subdomain = extract_subdomain(host_header)
    if not subdomain:
        return JSONResponse({"error": "Missing or invalid Host header"}, status_code=400)

    target_port = routes.get(subdomain)
    if not target_port:
        return JSONResponse({"error": f"No route found for {subdomain}.localhost"}, status_code=404)

    # build upstream URL and preserve query string
    url = f"http://127.0.0.1:{target_port}{request.url.path}"
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
            return JSONResponse({"error": f"Upstream request failed: {exc}"}, status_code=502)

    # Filter hop-by-hop headers
    excluded = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"}
    resp_headers = {k: v for k, v in proxy_resp.headers.items() if k.lower() not in excluded}

    return Response(content=proxy_resp.content, status_code=proxy_resp.status_code, headers=resp_headers)


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5555, reload=True)
