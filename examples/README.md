# Devhost Examples

This directory contains example integrations showing different ways to use Devhost.

## Examples

### 1. Zero-Config Flask (Recommended - v2.3+) (`example_zero_config_flask.py`)
The simplest way to run Flask with subdomain support - just one line:

```python
from devhost_cli.frameworks import run_flask
run_flask(app, name="myapp")  # → http://myapp.localhost
```

**Run:** `python examples/example_zero_config_flask.py`

### 2. Zero-Config FastAPI (v2.3+) (`example_zero_config_fastapi.py`)
Run FastAPI with auto-registration:

```python
from devhost_cli.frameworks import run_fastapi
run_fastapi(app, name="myapi")  # → http://myapi.localhost
```

**Run:** `python examples/example_zero_config_fastapi.py`

### 3. Zero-Config Generic Runner (v2.3+) (`example_zero_config_generic.py`)
Auto-detects your framework and runs appropriately:

```python
from devhost_cli.runner import run
run(app)  # Auto-detects Flask, FastAPI, or Django
```

**Run:** `python examples/example_zero_config_generic.py`

### 4. Flask-SocketIO (v2.3+) (`example_flask_socketio.py`)
Flask with WebSocket support via Flask-SocketIO:

```python
from flask_socketio import SocketIO
from devhost_cli.frameworks import run_flask

socketio = SocketIO(app)
run_flask(app, name="myapp", socketio=socketio)
```

**Run:** `python examples/example_flask_socketio.py`

### 5. Factory Function (`example_factory.py`)
The simplest way to get started with ASGI - creates a complete Devhost app:

```python
from devhost_cli.factory import create_devhost_app
app = create_devhost_app()
```

**Run:** `python examples/example_factory.py`

### 6. FastAPI Middleware (`example_fastapi_middleware.py`)
Add Devhost routing to your existing FastAPI app:

```python
from devhost_cli.middleware.asgi import DevhostMiddleware
app.add_middleware(DevhostMiddleware)
```

**Run:** `python examples/example_fastapi_middleware.py`

### 7. Starlette Integration (`example_starlette.py`)
Use Devhost with Starlette applications:

```python
from devhost import DevhostMiddleware
from starlette.applications import Starlette
app.add_middleware(DevhostMiddleware)
```

**Run:** `python examples/example_starlette.py`

### 8. Full Integration (`example_full_integration.py`)
Combine factory functions with custom routes:

```python
from devhost_cli.factory import enable_subdomain_routing, create_proxy_router
enable_subdomain_routing(app)
app.include_router(create_proxy_router())
```

**Run:** `python examples/example_full_integration.py`

### 9. Flask WSGI Integration (`example_flask.py`)
Add Devhost routing to your Flask application:

```python
from devhost_cli.middleware.wsgi import DevhostWSGIMiddleware
from flask import Flask

app = Flask(__name__)
app.wsgi_app = DevhostWSGIMiddleware(app.wsgi_app)
```

**Run:** `python examples/example_flask.py`

### 10. Django WSGI Integration (`example_django.py`)
Add Devhost routing to your Django application:

```python
from devhost_cli.middleware.wsgi import DevhostWSGIMiddleware
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
application = DevhostWSGIMiddleware(application)
```

**Run:** `python examples/example_django.py`

## Setup

```bash
# Install devhost with YAML support (for zero-config runner)
pip install devhost[yaml]

# Or with Flask/Django support
pip install devhost[flask,yaml]    # Flask + YAML
pip install devhost[django,yaml]   # Django + YAML

# Initialize project config (optional)
devhost init

# Run any example
python examples/example_zero_config_flask.py

# Access at:
# http://myapp.localhost:8000
```

## Features Demonstrated

- ✅ **Zero-config runner** (v2.3+) - One line to run with subdomain support
- ✅ **Auto-registration** - Routes registered on startup, cleaned on exit
- ✅ **Framework detection** - Auto-detects Flask, FastAPI, Django
- ✅ **Flask-SocketIO support** - WebSocket-enabled Flask apps
- ✅ Subdomain routing (ASGI & WSGI)
- ✅ Proxy functionality  
- ✅ Health checks
- ✅ Route management endpoints
- ✅ Custom middleware integration (ASGI & WSGI)
- ✅ Factory pattern usage (ASGI)
- ✅ Mixed custom + proxy routes
- ✅ Flask integration (WSGI)
- ✅ Django integration (WSGI)

## Understanding the `name` Parameter

The `name` parameter determines **your app's subdomain**. It can be **anything you want**!

```python
run_flask(app, name="myapp")     # → http://myapp.localhost
run_flask(app, name="api")       # → http://api.localhost
run_flask(app, name="frontend")  # → http://frontend.localhost
run_flask(app, name="sysgrow")   # → http://sysgrow.localhost
```

### Priority (highest to lowest):

| Priority | Source | Example |
|----------|--------|---------|
| 1️⃣ | `name` parameter | `run_flask(app, name="myapi")` |
| 2️⃣ | `devhost.yml` file | `name: myapp` in devhost.yml |
| 3️⃣ | Directory name | Uses current folder name |

### Key Points:

- **`name` does NOT need to match `devhost.yml`** - it overrides it!
- **Use any name you want** - it's just a subdomain identifier
- **Each app needs a unique name** - conflicts are handled automatically
- **Omit `name` to use defaults** - reads from devhost.yml or directory

### Examples:

```python
# Explicit name (recommended for clarity)
run_flask(app, name="sysgrow", socketio=socketio)  # → http://sysgrow.localhost

# Use devhost.yml config (if name: myapp is set)
run_flask(app, socketio=socketio)  # → http://myapp.localhost

# Multiple apps with different names
run_flask(frontend_app, name="frontend")  # → http://frontend.localhost
run_flask(api_app, name="api")            # → http://api.localhost
```
