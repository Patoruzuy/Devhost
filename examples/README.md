# Devhost Examples

This directory contains example integrations showing different ways to use Devhost v3.0.

## Quick Start

```bash
# Install devhost
pip install devhost

# Add a route
devhost add myapp 8000

# Access at:
# http://myapp.localhost:7777  (Gateway mode - default)
# http://myapp.localhost       (System mode - requires upgrade)
```

## Examples

### 1. Zero-Config Flask (`example_zero_config_flask.py`)
The simplest way to run Flask with subdomain support:

```python
from devhost_cli.frameworks import run_flask
run_flask(app, name="myapp")  # → http://myapp.localhost:7777
```

**Run:** `python examples/example_zero_config_flask.py`

### 2. Zero-Config FastAPI (`example_zero_config_fastapi.py`)
Run FastAPI with auto-registration:

```python
from devhost_cli.frameworks import run_fastapi
run_fastapi(app, name="myapi")  # → http://myapi.localhost:7777
```

**Run:** `python examples/example_zero_config_fastapi.py`

### 3. Zero-Config Generic Runner (`example_zero_config_generic.py`)
Auto-detects your framework and runs appropriately:

```python
from devhost_cli.runner import run
run(app)  # Auto-detects Flask, FastAPI, or Django
```

**Run:** `python examples/example_zero_config_generic.py`

### 4. Flask-SocketIO (`example_flask_socketio.py`)
Flask with WebSocket support via Flask-SocketIO:

```python
from flask_socketio import SocketIO
from devhost_cli.frameworks import run_flask

socketio = SocketIO(app)
run_flask(app, name="myapp", socketio=socketio)
```

**Run:** `python examples/example_flask_socketio.py`

### 5. Factory Function (`example_factory.py`)
Create a complete Devhost app with the factory:

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
from devhost_cli.middleware.asgi import DevhostMiddleware
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
# Install devhost with all optional dependencies
pip install devhost[tui,qr,tunnel]

# Start the router (Gateway mode)
devhost proxy start

# Run any example
python examples/example_zero_config_flask.py

# Access at http://myapp.localhost:7777
```

## Devhost v3.0 Modes

| Mode | URL Pattern | Port | Setup |
|------|-------------|------|-------|
| **Gateway** (default) | `http://myapp.localhost:7777` | 7777 | None |
| **System** | `http://myapp.localhost` | 80/443 | `devhost proxy upgrade --to system` |
| **External** | `http://myapp.localhost` | Custom | Your nginx/Traefik |

## Features Demonstrated

- ✅ **Zero-config runner** - One line to run with subdomain support
- ✅ **Auto-registration** - Routes registered on startup, cleaned on exit
- ✅ **Framework detection** - Auto-detects Flask, FastAPI, Django
- ✅ **WebSocket support** - Full bidirectional WebSocket proxying
- ✅ **Flask-SocketIO** - WebSocket-enabled Flask apps
- ✅ **Subdomain routing** - Both ASGI & WSGI
- ✅ **Proxy functionality**  
- ✅ **Health checks**
- ✅ **Route management**
- ✅ **Custom middleware** - ASGI & WSGI
- ✅ **Factory pattern**

## Understanding the `name` Parameter

The `name` parameter determines **your app's subdomain**:

```python
run_flask(app, name="myapp")     # → http://myapp.localhost:7777
run_flask(app, name="api")       # → http://api.localhost:7777
run_flask(app, name="frontend")  # → http://frontend.localhost:7777
```

### Priority (highest to lowest):

| Priority | Source | Example |
|----------|--------|---------|
| 1️⃣ | `name` parameter | `run_flask(app, name="myapi")` |
| 2️⃣ | `devhost.yml` file | `name: myapp` |
| 3️⃣ | Directory name | Uses current folder name |

## New v3.0 Features

### Tunnel Integration
Expose your local app to the internet:

```bash
devhost tunnel start myapp --provider cloudflared
```

### TUI Dashboard
Interactive terminal dashboard:

```bash
pip install devhost[tui]
devhost dashboard
```

### QR Code for Mobile
Generate QR code for LAN access:

```bash
pip install devhost[qr]
devhost qr myapp
```
