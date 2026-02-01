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

### 4. Factory Function (`example_factory.py`)
The simplest way to get started with ASGI - creates a complete Devhost app:

```python
from devhost_cli.factory import create_devhost_app
app = create_devhost_app()
```

**Run:** `python examples/example_factory.py`

### 5. FastAPI Middleware (`example_fastapi_middleware.py`)
Add Devhost routing to your existing FastAPI app:

```python
from devhost_cli.middleware.asgi import DevhostMiddleware
app.add_middleware(DevhostMiddleware)
```

**Run:** `python examples/example_fastapi_middleware.py`

### 6. Starlette Integration (`example_starlette.py`)
Use Devhost with Starlette applications:

```python
from devhost import DevhostMiddleware
from starlette.applications import Starlette
app.add_middleware(DevhostMiddleware)
```

**Run:** `python examples/example_starlette.py`

### 7. Full Integration (`example_full_integration.py`)
Combine factory functions with custom routes:

```python
from devhost_cli.factory import enable_subdomain_routing, create_proxy_router
enable_subdomain_routing(app)
app.include_router(create_proxy_router())
```

**Run:** `python examples/example_full_integration.py`

### 8. Flask WSGI Integration (`example_flask.py`)
Add Devhost routing to your Flask application:

```python
from devhost_cli.middleware.wsgi import DevhostWSGIMiddleware
from flask import Flask

app = Flask(__name__)
app.wsgi_app = DevhostWSGIMiddleware(app.wsgi_app)
```

**Run:** `python examples/example_flask.py`

### 9. Django WSGI Integration (`example_django.py`)
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
- ✅ Subdomain routing (ASGI & WSGI)
- ✅ Proxy functionality  
- ✅ Health checks
- ✅ Route management endpoints
- ✅ Custom middleware integration (ASGI & WSGI)
- ✅ Factory pattern usage (ASGI)
- ✅ Mixed custom + proxy routes
- ✅ Flask integration (WSGI)
- ✅ Django integration (WSGI)
