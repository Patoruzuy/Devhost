# Contributing to Devhost

Thank you for your interest in contributing to Devhost! This document provides guidelines and instructions for contributing.

## Before Submitting a Pull Request

### 1. Run Linting

**Required before every PR submission:**

```bash
# Check for linting issues
python -m ruff check .

# Check formatting
python -m ruff format --check .

# Auto-fix formatting issues (optional)
python -m ruff format .
```

All linting checks must pass. No warnings or errors should be present.

### 2. Run Tests

**Required before every PR submission:**

```bash
# Run all tests
python -m unittest discover

# Run specific test file (optional)
python -m unittest tests.test_app

# Run with verbose output (optional)
python -m unittest discover -v
```

All tests must pass (100% pass rate). Do not submit PRs with failing tests.

### 3. Run Security Tests

**Critical for security-related PRs:**

Security tests validate protection against SSRF, header injection, privilege escalation, and other vulnerabilities. All security tests must pass.

```bash
# Run full security test suite
python -m unittest discover -s tests -p "test_security_*.py" -v

# Run specific security tests
python -m unittest tests.test_security_ssrf -v           # SSRF protection
python -m unittest tests.test_security_headers -v        # Host header validation
python -m unittest tests.test_security_schemes -v        # URL scheme validation

# Run all tests including security
python -m unittest discover -v
```

**Security test requirements:**
- All SSRF protection tests must pass (blocks metadata endpoints, private IPs)
- All hostname validation tests must pass (prevents header injection)
- All URL scheme tests must pass (rejects file://, ftp://, etc.)
- Windows-specific tests may be skipped on non-Windows platforms

**Security-related changes require:**
- New test coverage for new attack vectors
- Update to [docs/security-configuration.md](docs/security-configuration.md)
- Mention in [CHANGELOG.md](CHANGELOG.md) with severity rating

### 4. Update Dependencies

**Weekly automated scans** run every Monday via [.github/workflows/security-scan.yml](.github/workflows/security-scan.yml).

**Responding to vulnerability alerts:**

When the automated security scan creates a GitHub issue:

1. Review the issue details (package name, CVE, severity)
2. Update the affected package:
   ```bash
   pip install --upgrade <package-name>
   ```
3. Verify the fix resolves the vulnerability:
   ```bash
   pip-audit --desc
   ```
4. Run the full test suite to ensure no regressions:
   ```bash
   python -m unittest discover
   ```
5. Commit with security prefix:
   ```bash
   git commit -m "security: Update <package> to fix CVE-YYYY-XXXXX"
   ```

**Manual dependency updates:**

```bash
# Update specific package
pip install --upgrade httpx

# Update all router dependencies
pip install --upgrade -r router/requirements.txt

# Update development dependencies
pip install --upgrade -e ".[dev,all]"

# Verify no vulnerabilities after updates
pip-audit --desc
```

**Viewing SBOM (Software Bill of Materials):**

The weekly security scan generates SBOMs for supply chain transparency:

- Download from [GitHub Actions artifacts](https://github.com/yourusername/devhost/actions/workflows/security-scan.yml)
- `sbom-cyclonedx.json` - Machine-readable format for automated tools
- `sbom-cyclonedx.xml` - Compliance documentation format

**GitHub Actions security:**

All GitHub Actions are pinned to commit SHAs to prevent supply chain attacks:

```yaml
# Example: pinned to specific commit
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
```

When updating action versions:
1. Check the official release page for the new version's commit SHA
2. Verify the SHA matches the tagged release
3. Update both the SHA and the version comment
4. Test the workflow to ensure it still works

**Dependency pinning limitations:**

Note: Automated dependency pinning with `pip-tools` is currently blocked due to Python 3.13 compatibility issues. Manual dependency management is recommended until this is resolved. See [docs/PHASE3-PLAN.md](docs/PHASE3-PLAN.md) for details.

### 5. Test Your Changes Manually

Before submitting, verify your changes work as expected:

```bash
# Install in editable mode
python -m pip install -e ".[dev,all]"

# Start the router
make start
# OR
uvicorn router.app:app --port 7777 --reload

# Test your changes
devhost add myapp 8000
devhost open myapp
```

### 6. Update Documentation

If your changes affect user-facing functionality:

- Update [README.md](README.md) if adding new features
- Update [.github/copilot-instructions.md](.github/copilot-instructions.md) for architectural changes
- Update [examples/](examples/) if adding new integration patterns
- Add docstrings to new functions/classes

### 7. Commit Message Guidelines

Write clear, descriptive commit messages:

```bash
# Good examples:
git commit -m "Add WebSocket proxy support to router"
git commit -m "Fix: Handle port conflicts in Windows environment"
git commit -m "Docs: Update README with tunnel provider examples"

# Bad examples:
git commit -m "fix bug"
git commit -m "update"
git commit -m "wip"
```

**Format:**
- Start with a verb (Add, Fix, Update, Remove, Refactor)
- Keep first line under 72 characters
- Add detailed explanation in the body if needed

## Development Workflow

### Setting Up Your Environment

1. **Fork and clone the repository:**

```bash
git clone https://github.com/YOUR_USERNAME/devhost.git
cd devhost
```

2. **Create a virtual environment:**

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
```

3. **Upgrade packaging tools (recommended):**
Some Python/venv installs (notably Python 3.12+) create environments with `pip` but without `setuptools`/`wheel`. If you ever see errors like `BackendUnavailable: Cannot import 'setuptools.build_meta'`, run:

```bash
python -m pip install --upgrade pip setuptools wheel
```

4. **Install development dependencies:**

```bash
python -m pip install -e ".[dev,all]"
```

5. **Create a feature branch:**

```bash
git checkout -b feature/your-feature-name
```

### Making Changes

1. **Write your code** following the existing code style
2. **Add tests** for new functionality
3. **Update documentation** as needed
4. **Run linting and tests** (see above)
5. **Commit your changes** with clear messages

### Submitting Your PR

1. **Push to your fork:**

```bash
git push origin feature/your-feature-name
```

2. **Create a Pull Request** on GitHub with:
   - Clear description of what changed and why
   - Reference to related issues (if any)
   - Screenshots/examples for UI changes
   - Confirmation that linting and tests pass

### Copilot Code Review (Optional)

If GitHub Copilot code review is enabled for your repository/org, you can request it on a pull request the same way you request a human reviewer:

- Open a PR
- Add **Copilot** as a reviewer (or use the PR UI action that requests a Copilot review, if present)

Availability and UI labels vary by GitHub plan and org settings.

3. **Respond to feedback** from maintainers

## Code Style Guidelines

### Python Style

- Follow PEP 8 conventions
- Use type hints where appropriate
- Maximum line length: 120 characters (enforced by ruff)
- Use double quotes for strings
- 4 spaces for indentation (no tabs)

### Naming Conventions

- Functions/methods: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`

### Example:

```python
from typing import Optional

class RouteManager:
    """Manages route registration and lifecycle."""
    
    DEFAULT_PORT = 7777
    
    def __init__(self, config_path: str):
        self._config_path = config_path
    
    def add_route(self, name: str, port: int) -> Optional[dict]:
        """Add a new route to the configuration.
        
        Args:
            name: Route name (subdomain)
            port: Target port number
            
        Returns:
            Route configuration dict if successful, None otherwise
        """
        # Implementation here
        pass
```

## Testing Guidelines

### Writing Tests

- Use `unittest` framework
- Put tests in `tests/` directory
- Name test files: `test_*.py`
- Name test methods: `test_*`
- Use descriptive test names

### Test Example:

```python
import unittest
from devhost_cli.validation import validate_port

class TestValidation(unittest.TestCase):
    def test_validate_port_accepts_valid_port(self):
        """Should accept ports in valid range (1-65535)"""
        self.assertTrue(validate_port(8000))
        self.assertTrue(validate_port(3000))
    
    def test_validate_port_rejects_invalid_port(self):
        """Should reject ports outside valid range"""
        self.assertFalse(validate_port(0))
        self.assertFalse(validate_port(70000))
```

## Project Structure

```
devhost/
├── devhost_cli/          # CLI package
│   ├── frameworks/       # Framework-specific helpers
│   ├── middleware/       # ASGI/WSGI middleware
│   └── router/           # Router core logic
├── router/               # FastAPI router app
├── tests/                # Test suite
├── examples/             # Usage examples
├── caddy/                # Caddy configuration
└── completions/          # Shell completions
└──devhost_cli/     # CLI package
    ├── cli.py            # Core CLI commands (add, remove, list)
    ├── config.py         # Legacy config handling (devhost.json)
    ├── state.py          # v3 state management (~/.devhost/state.yml)
    ├── caddy.py          # Caddy lifecycle management
    ├── tunnel.py         # cloudflared/ngrok/localtunnel integration
    ├── runner.py         # Framework app runner
    ├── router_manager.py # Router process management
    ├── validation.py     # Target/port validation
    ├── platform.py       # Platform detection
    └── windows.py        # Windows-specific helpers
└── devhost_tui/          # TUI dashboard package
    └── app.py            # TUI dashboard implementation
    └── modals.py         # TUI data models
    └── scanners.py       # TUI scanning utilities
    └── widgets.py        # TUI custom widgets
└── router/               # FastAPI router app
    ├── app.py            # FastAPI proxy with WebSocket support
    ├── requirements.txt  # Router dependencies (httpx, websockets)
    └── Dockerfile        # Container build (port 7777)

```

## Getting Help

- **Questions?** Open a [Discussion](https://github.com/Patoruzuy/devhost/discussions)
- **Bug reports?** Open an [Issue](https://github.com/Patoruzuy/devhost/issues)
- **Feature requests?** Open an [Issue](https://github.com/Patoruzuy/devhost/issues) with `[Feature Request]` prefix

## License

By contributing to Devhost, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Devhost! 🎉
