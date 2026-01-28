from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
import httpx
import json
import uvicorn
from typing import Optional

app = FastAPI()


def extract_subdomain(host_header: Optional[str]) -> Optional[str]:
    if not host_header:
        return None
    # strip port if present
    host_only = host_header.split(":")[0]
    # take first label (subdomain)
    parts = host_only.split(".")
    return parts[0] if parts else None


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def wildcard_proxy(request: Request, full_path: str):
    # Load routes on each request so CLI updates take effect immediately
    try:
        with open("devhost.json") as f:
            routes = json.load(f)
    except Exception:
        routes = {}

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
