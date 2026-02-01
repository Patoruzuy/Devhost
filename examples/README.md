# Devhost Examples

This directory contains example integrations showing different ways to use Devhost.

## Examples

### 1. Factory Function (`example_factory.py`)
The simplest way to get started - creates a complete Devhost app:

```python
from devhost_cli.factory import create_devhost_app
app = create_devhost_app()
```

**Run:** `python examples/example_factory.py`

### 2. FastAPI Middleware (`example_fastapi_middleware.py`)
Add Devhost routing to your existing FastAPI app:

```python
from devhost_cli.middleware.asgi import DevhostMiddleware
app.add_middleware(DevhostMiddleware)
```

**Run:** `python examples/example_fastapi_middleware.py`

### 3. Starlette Integration (`example_starlette.py`)
Use Devhost with Starlette applications:

```python
from devhost import DevhostMiddleware
from starlette.applications import Starlette
app.add_middleware(DevhostMiddleware)
```

**Run:** `python examples/example_starlette.py`

### 4. Full Integration (`example_full_integration.py`)
Combine factory functions with custom routes:

```python
from devhost_cli.factory import enable_subdomain_routing, create_proxy_router
enable_subdomain_routing(app)
app.include_router(create_proxy_router())
```

**Run:** `python examples/example_full_integration.py`

### 5. Flask WSGI Integration (`example_flask.py`)
Add Devhost routing to your Flask application:

```python
from devhost_cli.middleware.wsgi import DevhostWSGIMiddleware
from flask import Flask

app = Flask(__name__)
app.wsgi_app = DevhostWSGIMiddleware(app.wsgi_app)
```

**Run:** `python examples/example_flask.py`

### 6. Django WSGI Integration (`example_django.py`)
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
# Install devhost with ASGI support
pip install devhost

# Or with Flask/Django support
pip install devhost[flask]    # Flask
pip install devhost[django]   # Django

# Run any example
python examples/example_factory.py

# Configure routes
devhost add myapp 3000
devhost add api 8000

# Access at:
# http://myapp.localhost
# http://api.localhost
```

## Features Demonstrated

- ✅ Subdomain routing (ASGI & WSGI)
- ✅ Proxy functionality  
- ✅ Health checks
- ✅ Route management endpoints
- ✅ Custom middleware integration (ASGI & WSGI)
- ✅ Factory pattern usage (ASGI)
- ✅ Mixed custom + proxy routes
- ✅ Flask integration (WSGI)
- ✅ Django integration (WSGI)
