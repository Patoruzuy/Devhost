# Phase 5: PyPI Package Development Plan

## 🎯 Overview

Transform Devhost into a distributable Python package that developers can install via `pip install devhost` and use in multiple ways:
- ✅ As a CLI tool (current functionality - no changes)
- ✅ As ASGI middleware in FastAPI/Starlette apps
- ✅ As WSGI middleware for Flask/Django
- ✅ As factory functions for creating router instances
- ✅ All features in one package (Option A)

## 📊 Current State

**Version**: 2.0.0  
**Branch**: `pypi-package`  
**Tests**: 19/19 passing ✅  
**Lint**: 0 errors ✅  
**Phases Complete**: 1-4 (100%)

## 🎁 What We're Building

After Phase 5, developers will be able to:

```python
# Install once
pip install devhost

# Use as CLI (existing - unchanged)
devhost add api 8001

# Use as FastAPI middleware (NEW)
from devhost import DevhostMiddleware
app.add_middleware(DevhostMiddleware, routes={"api": 8001})

# Use factory pattern (NEW)
from devhost import create_devhost_app
router = create_devhost_app(routes={"api": 8001, "rpi": "192.168.1.100:8080"})

# Use helper function (NEW)
from devhost import enable_subdomain_routing
enable_subdomain_routing(app, routes={"api": 8001})
Implementation Steps
Step 1: Refactor Router for Reusability
Goal: Extract router components into importable modules.

Current: Single router/app.py (393 lines)

Target: Modular structure
devhost_cli/
└── router/          # NEW directory
    ├── __init__.py
    ├── core.py      # Main router logic
    ├── cache.py     # RouteCache class
    ├── metrics.py   # Metrics class
    └── utils.py     # Helper functions (parse_target, extract_subdomain, load_domain)

Files to create:

devhost_cli/router/init.py - Exports for package users
devhost_cli/router/utils.py - Pure functions (no state)
devhost_cli/router/cache.py - RouteCache class
devhost_cli/router/metrics.py - Metrics class
devhost_cli/router/core.py - FastAPI app creation
Files to modify:

router/app.py - Keep as entry point, import from new modules
Success criteria:

All 19 tests still pass
Router still works: python router/app.py
Functions importable: from devhost_cli.router import parse_target
Step 2: Create ASGI Middleware
Goal: Enable FastAPI/Starlette integration.

New file: devhost_cli/middleware/asgi.py

Features:

Subdomain-based routing
Proxy to target services
Request ID tracking
Metrics collection
Configurable routes

API:
class DevhostMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        routes: dict | callable,
        domain: str = "localhost",
        enable_metrics: bool = True
    )

Test file: tests/test_middleware_asgi.py (10+ tests)

Step 3: Create WSGI Middleware
Goal: Enable Flask/Django integration.

New file: devhost_cli/middleware/wsgi.py

Features:

WSGI-compatible middleware
Synchronous HTTP proxying
Works with requests library

API:
class DevhostWSGIMiddleware:
    def __init__(
        self,
        app,
        routes: dict,
        domain: str = "localhost"
    )

Test file: tests/test_middleware_wsgi.py (8+ tests)

Step 4: Create Factory Functions
Goal: Provide convenience functions.

New file: devhost_cli/factory.py

Functions:
def create_devhost_app(routes: dict, domain: str = "localhost", **kwargs) -> FastAPI
def create_proxy_router(routes: dict, domain: str = "localhost") -> APIRouter
def enable_subdomain_routing(app, routes: dict, domain: str = "localhost") -> None

Test file: tests/test_factory.py (6+ tests)

Step 5: Update Package Exports
Goal: Clean API for pip users.

File to modify: __init__.py

New exports:
from .middleware.asgi import DevhostMiddleware
from .middleware.wsgi import DevhostWSGIMiddleware
from .factory import (
    create_devhost_app,
    create_proxy_router,
    enable_subdomain_routing
)
from .router import extract_subdomain, parse_target

__version__ = "2.1.0"

__all__ = [
    "DevhostMiddleware",
    "DevhostWSGIMiddleware",
    "create_devhost_app",
    "create_proxy_router",
    "enable_subdomain_routing",
    "extract_subdomain",
    "parse_target",
]

Step 6: Update pyproject.toml for PyPI
File to modify: pyproject.toml

Changes:

Bump version to 2.1.0
Add package description for PyPI
Add keywords and classifiers
Specify entry points
Add project URLs

Key sections:
[project]
name = "devhost"
version = "2.1.0"
description = "Secure, flexible local domain routing for developers"
keywords = ["development", "subdomain", "proxy", "fastapi", "flask"]

Step 7: Create Usage Examples
Goal: Show developers how to use the package.

New directory: examples/

Files to create:

examples/fastapi_example.py - FastAPI middleware usage
examples/flask_example.py - Flask WSGI middleware usage
examples/standalone_example.py - Factory pattern usage
README.md - Examples documentation
Step 8: Update Documentation
Files to modify:

README.md - Add "Using as a Package" section
CHANGELOG.md - Document Phase 5 changes
New files:

README_PYPI.md - PyPI-specific README
docs/MIDDLEWARE_GUIDE.md - Detailed middleware docs
Step 9: Add Tests
Goal: Maintain 100% test pass rate, increase coverage.

New test files:

tests/test_middleware_asgi.py (10+ tests)
tests/test_middleware_wsgi.py (8+ tests)
tests/test_factory.py (6+ tests)
Target: 19 → 43+ tests

Step 10: GitHub Actions for PyPI
Goal: Automate package publishing.

New file: .github/workflows/publish.yml

Triggers:

Git tags matching v*
Manual workflow dispatch
Steps:

Run all tests
Build package
Publish to TestPyPI (test)
Publish to PyPI (production)
✅ Success Criteria
 All existing 19 tests pass
 24+ new tests added (total 43+)
 100% backward compatibility
 Package builds without errors: python -m build
 Can install locally: pip install -e .
 Examples work
 Documentation complete
 Published to TestPyPI
 Published to PyPI
📅 Timeline
Day 1-2: Steps 1-2 (Router refactoring + ASGI middleware)
Day 3-4: Steps 3-5 (WSGI middleware + Factory + Exports)
Day 5: Steps 6-7 (PyPI config + Examples)
Day 6-7: Steps 8-10 (Docs + Tests + Publishing)

🎯 Target Version
Current: 2.0.0
Target: 2.1.0 (new features, backward compatible)

🔄 Backward Compatibility
CLI: No changes! Works exactly as before

Router: No changes! Entry point preserved

New: Package imports (optional for users)
from devhost import DevhostMiddleware
from devhost import create_devhost_app

## 📦 Post-Phase 5: Devhost
📦 Package Structure (After Phase 5)
devhost/
├── devhost_cli/
│   ├── __init__.py           # Main exports (updated)
│   ├── cli/                  # CLI tools (existing)
│   ├── router/               # Router core (NEW)
│   │   ├── __init__.py
│   │   ├── core.py
│   │   ├── cache.py
│   │   ├── metrics.py
│   │   └── utils.py
│   ├── middleware/           # Framework integrations (NEW)
│   │   ├── __init__.py
│   │   ├── asgi.py
│   │   └── wsgi.py
│   └── factory.py            # Factory functions (NEW)
├── router/
│   └── app.py                # Entry point (imports from devhost_cli.router)
├── examples/                 # Usage examples (NEW)
├── tests/                    # 43+ tests
├── pyproject.toml            # PyPI config (updated)
└── README.md    

Write a professional test plan
## 📋 Test Plan for Phase 5: PyPI Package Development
### Objectives
- Ensure all existing functionality remains intact (100% backward compatibility).
- Validate new features: ASGI/WSGI middleware, factory functions.
- Achieve 100% test pass rate with expanded coverage (43+ tests).
### Test Categories
1. **Unit Tests**
    - Test individual functions in `utils.py`, `cache.py`, `metrics.py`.
    - Validate input/output for `parse_target`, `extract_subdomain`.
    - Test middleware classes for correct initialization and behavior.
    - Test factory functions for correct app/router creation.   
2. **Integration Tests**
    - Test router functionality via `router/app.py`.
    - Validate middleware integration with FastAPI and Flask apps.
    - Test end-to-end request routing through middleware.
3. **CLI Tests**
    - Ensure existing CLI commands work as before.
    - Validate no regressions in CLI behavior.
4. **Documentation Tests**
    - Verify code examples in documentation run without errors.
    - Ensure README and usage guides are accurate.  



🎓 Next Steps
✅ Branch created: pypi-package
✅ Plan document created: PHASE5-PLAN.md
⏭️ Start Step 1: Router refactoring
⏭️ Implement Steps 2-10
⏭️ Test and publish
Status: 📋 Planning Complete - Ready for Implementation
Next Action: Start Step 1 (Router Refactoring)

