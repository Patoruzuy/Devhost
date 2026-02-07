# Devhost Examples

This directory contains executable examples showing how to integrate Devhost v3.0 into various Python frameworks.

## Why Integrate?
While you can always use the `devhost add` CLI command manually, integration allows your app to:
1. **Auto-register**: Automatically add its subdomain to Devhost on startup.
2. **Find a Port**: Automatically find an available port if none is specified.
3. **Start the Router**: Ensure the Devhost Gateway router is running.

---

## Integration Patterns

### 1. The "Zero-Config" Runner (Recommended)
This is the easiest way to wrap your existing application. It auto-detects if you're using Flask, FastAPI, or Django.

```python
from devhost_cli.runner import run

# ... your app definition ...

if __name__ == "__main__":
    run(app, name="myapp")  # Accessible at http://myapp.localhost:7777
```
**See**: `example_zero_config_generic.py`

### 2. Framework-Specific Auto-Detection
The runner automatically detects your framework and runs it appropriately.

**Flask**:
```python
from devhost_cli.runner import run
run(app, name="frontend")
```
**See**: `example_zero_config_flask.py`

**FastAPI**:
```python
from devhost_cli.runner import run
run(app, name="api")
```
**See**: `example_zero_config_fastapi.py`

### 3. Middleware Integration
Add Devhost logic directly into your app's middleware stack. This is useful for capturing requests before they hit your routes.

```python
from devhost_cli.middleware.asgi import DevhostMiddleware
app.add_middleware(DevhostMiddleware)
```
**See**: `example_fastapi_middleware.py`

### 4. WebSocket Support
Devhost natively supports WebSockets. Here is how to use it with `Flask-SocketIO`.

```python
from flask_socketio import SocketIO
from devhost_cli.runner import run

socketio = SocketIO(app)
run(app, name="chat", socketio=socketio)
```
**See**: `example_flask_socketio.py`

---

## Running the Examples

1. **Install dependencies**:
   ```bash
   pip install flask fastapi uvicorn flask-socketio
   pip install -e .
   ```

2. **Run an example**:
   ```bash
   python examples/example_zero_config_flask.py
   ```

3. **Check the Dashboard**:
   Open a separate terminal and run `devhost dashboard` to see the route appear live.
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
run(app, name="myapp")     # → http://myapp.localhost:7777
run(app, name="api")       # → http://api.localhost:7777
run(app, name="frontend")  # → http://frontend.localhost:7777
```

### Priority (highest to lowest):

| Priority | Source | Example |
|----------|--------|---------|
| 1️⃣ | `name` parameter | `run(app, name="myapi")` |
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
