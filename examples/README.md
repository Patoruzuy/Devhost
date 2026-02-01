# Devhost Usage Examples

Examples demonstrating how to use Devhost as a Python package in your applications.

## Standalone Proxy Server

Run Devhost as a standalone reverse proxy:

```python
from devhost import create_devhost_app
import uvicorn

app = create_devhost_app()
uvicorn.run(app, host="127.0.0.1", port=5555)
```

## FastAPI Integration

Add subdomain routing to your FastAPI application:

```python
from fastapi import FastAPI, Request
from devhost import enable_subdomain_routing

app = FastAPI()
enable_subdomain_routing(app)

@app.get("/")
def read_root(request: Request):
    devhost_info = request.scope.get("devhost", {})
    subdomain = devhost_info.get("subdomain")
    target = devhost_info.get("target")
    
    return {
        "message": f"Hello from {subdomain or 'main'}!",
        "subdomain": subdomain,
        "target": target
    }
```

## Starlette Integration

Use with Starlette applications:

```python
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from devhost import DevhostMiddleware

async def homepage(request):
    subdomain = request.scope.get("devhost", {}).get("subdomain")
    return JSONResponse({"subdomain": subdomain})

app = Starlette(routes=[
    Route("/", homepage),
])

app.add_middleware(DevhostMiddleware)
```

## Custom ASGI Integration

Wrap any ASGI application:

```python
from devhost import enable_subdomain_routing

async def my_asgi_app(scope, receive, send):
    if scope["type"] == "http":
        subdomain = scope.get("devhost", {}).get("subdomain")
        
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        
        body = f'{{"subdomain": "{subdomain}"}}'.encode()
        await send({
            "type": "http.response.body",
            "body": body,
        })

# Wrap with Devhost middleware
app = enable_subdomain_routing(my_asgi_app)
```

## See Also

- [example_fastapi.py](example_fastapi.py) - Complete FastAPI example
- [example_proxy.py](example_proxy.py) - Standalone proxy example
- [example_starlette.py](example_starlette.py) - Starlette example
