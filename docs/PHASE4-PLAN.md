# Phase 4 Security Implementation Plan

**Status**: PLANNING  
**Target Start**: 2026-02-12 (Week 4)  
**Priority**: LOW severity + Additional hardening + Performance optimization  
**Branch**: feature/v3-architecture (continuing)  

**Phase 3 Status**: ✅ COMPLETE (7/10 tasks, 3 skipped/enterprise)

---

## Overview

Phase 4 focuses on remaining low-severity security enhancements, performance optimizations, and production readiness improvements. This phase completes the security audit recommendations and prepares the codebase for v3.0 release.

**Previous Phases**:
1. ✅ **Phase 1 (COMPLETE)**: SSRF, scheme validation, hostname validation, privilege escalation
2. ✅ **Phase 2 (COMPLETE)**: Log sanitization, file permissions, rate limiting
3. ✅ **Phase 3 (COMPLETE)**: Supply chain security, certificates, headers, input sanitization

---

## Priority 1: Security Audit Recommendations

### L-11: Executable Path Validation ⭐ HIGH VALUE

**Risk**: Malicious executables could be run from untrusted locations  
**Impact**: Code execution via PATH manipulation  
**Severity**: MEDIUM (mitigated by OS-level permissions)

**Implementation**:
- Add `validate_executable()` function to `devhost_cli/utils.py`
- Verify executable exists and is executable
- Warn if executable is in user-writable location (Windows)
- Integrate with Caddy, cloudflared, ngrok, localtunnel startup

**Code**:
```python
def validate_executable(exe_path: str) -> tuple[bool, str]:
    """Validate executable is safe to run
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    path = Path(exe_path)
    
    # Must exist
    if not path.exists():
        return False, f"Executable not found: {exe_path}"
    
    # Must be executable (Unix)
    if os.name != 'nt' and not os.access(path, os.X_OK):
        return False, f"File is not executable: {exe_path}"
    
    # Warn if in user-writable location (Windows)
    if os.name == 'nt':
        user_dirs = [Path.home(), Path.cwd()]
        if any(str(path).startswith(str(d)) for d in user_dirs):
            return True, f"WARNING: Executable {path.name} is in user-writable location"
    
    return True, ""
```

**Tests**:
- `test_validate_executable_exists()`
- `test_validate_executable_not_found()`
- `test_validate_executable_not_executable()` (Unix)
- `test_validate_executable_user_writable_warning()` (Windows)

**Files to modify**:
- `devhost_cli/utils.py` - add validation function
- `devhost_cli/caddy_lifecycle.py` - validate before Caddy start
- `devhost_cli/tunnel.py` - validate before tunnel start
- `tests/test_utils.py` - add validation tests

**Breaking Change**: NO (warnings only)  
**Migration**: N/A

---

### L-12: Subprocess Timeout Enforcement

**Risk**: Hanging subprocesses cause resource exhaustion  
**Impact**: DoS via indefinite subprocess hang  
**Severity**: LOW (rare in practice)

**Implementation**:
- Add `timeout=30` to all `subprocess.run()` calls
- Add `timeout=60` to long-running operations (Caddy validation)
- Handle `TimeoutExpired` exceptions gracefully

**Pattern**:
```python
try:
    result = subprocess.run(
        [...],
        timeout=30,  # seconds
        check=False,
        capture_output=True
    )
except subprocess.TimeoutExpired:
    logger.error("Command timed out after 30 seconds")
    return False
```

**Files to modify**:
- `devhost_cli/caddy_lifecycle.py` - add timeouts to all subprocess calls
- `devhost_cli/windows.py` - add timeouts to DNS/hosts file operations
- `devhost_cli/tunnel.py` - long timeout for tunnel startup (60s)

**Tests**:
- Mock subprocess to raise TimeoutExpired
- Verify error handling

**Breaking Change**: NO  
**Migration**: N/A

---

### L-13: Input Length Limits

**Risk**: Excessively long inputs cause buffer-like issues downstream  
**Impact**: DoS via memory exhaustion in DNS/routing systems  
**Severity**: LOW (OS limits provide protection)

**Implementation**:
- Add length limits to `validation.py`
- Validate before saving to config

**Code**:
```python
MAX_HOSTNAME_LENGTH = 253  # RFC 1035
MAX_ROUTE_NAME_LENGTH = 63  # DNS label limit
MAX_URL_LENGTH = 2048  # Common browser limit

def validate_route_name(name: str) -> tuple[bool, str]:
    """Validate route name length and format"""
    if len(name) > MAX_ROUTE_NAME_LENGTH:
        return False, f"Route name too long (max {MAX_ROUTE_NAME_LENGTH} chars)"
    
    if not name.replace('-', '').replace('_', '').isalnum():
        return False, "Route name must be alphanumeric (with - and _)"
    
    return True, ""
```

**Tests**:
- `test_route_name_max_length()`
- `test_hostname_max_length()`
- `test_url_max_length()`

**Files to modify**:
- `devhost_cli/validation.py` - add length limits
- `devhost_cli/cli.py` - call validation before config save
- `tests/test_validation.py` - add length limit tests

**Breaking Change**: NO (current inputs are short)  
**Migration**: N/A

---

## Priority 2: Performance Optimization

### L-14: HTTP Client Connection Pooling

**Current**: `httpx.AsyncClient` with default limits  
**Improvement**: Tune connection pooling for production load

**Implementation**:
```python
# router/app.py
http_client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_keepalive_connections=100,  # Up from 20
        max_connections=500,            # Up from 100
        keepalive_expiry=30.0           # Seconds
    ),
    timeout=httpx.Timeout(60.0, connect=10.0)
)
```

**Tests**:
- Load test with `locust` or `hey`
- Measure throughput before/after

**Breaking Change**: NO  
**Migration**: N/A

---

### L-15: Route Lookup Optimization

**Current**: Linear search through routes dictionary  
**Improvement**: Use cached lookups for hot paths

**Implementation**:
- Cache domain extraction from Host header
- Pre-compile regex patterns for route matching
- Use `lru_cache` for repeated lookups

**Code**:
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def extract_subdomain(host: str, domain: str) -> str | None:
    """Extract subdomain from Host header with caching"""
    # ... existing logic ...
```

**Tests**:
- Benchmark route lookup performance
- Verify cache hit rates

**Files to modify**:
- `router/app.py` - add caching
- `devhost_cli/router/utils.py` - add caching utilities

**Breaking Change**: NO  
**Migration**: N/A

---

## Priority 3: Observability Improvements

### L-16: Structured Logging

**Current**: String-based logging  
**Improvement**: JSON-structured logs for production

**Implementation**:
```python
# Enable via DEVHOST_LOG_FORMAT=json
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None)
        }
        return json.dumps(log_entry)
```

**Environment Variables**:
- `DEVHOST_LOG_FORMAT=json` - Enable JSON logging
- `DEVHOST_LOG_FORMAT=text` - Default text logging

**Tests**:
- Verify JSON output format
- Verify request ID inclusion

**Breaking Change**: NO (opt-in)  
**Migration**: N/A

---

### L-17: Metrics Endpoint Enhancements

**Current**: Basic `/metrics` endpoint  
**Improvement**: Add more detailed metrics

**Metrics to add**:
- Request latency histogram (p50, p95, p99)
- Error rate by route
- WebSocket connection duration
- SSRF block count by reason
- Certificate expiration alerts

**Implementation**:
```python
METRICS = {
    "requests_total": 0,
    "errors_total": 0,
    "latency_p50": 0.0,
    "latency_p95": 0.0,
    "latency_p99": 0.0,
    "ssrf_blocks_total": 0,
    "websocket_connections_active": 0,
    "cert_expiring_count": 0
}
```

**Tests**:
- Verify metrics incremented
- Verify percentile calculations

**Breaking Change**: NO (additive)  
**Migration**: N/A

---

## Priority 4: Production Readiness

### L-18: Health Check Enhancements

**Current**: Basic `/health` endpoint  
**Improvement**: Detailed health checks

**Implementation**:
```python
@app.get("/health")
def health_check():
    checks = {
        "router": "healthy",
        "config": check_config_readable(),
        "routes": check_routes_valid(),
        "certificates": check_certs_not_expired(),
        "upstream": check_upstream_reachable()  # Sample check
    }
    
    all_healthy = all(v == "healthy" for v in checks.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        {"status": "healthy" if all_healthy else "degraded", "checks": checks},
        status_code=status_code
    )
```

**Tests**:
- Mock failing health checks
- Verify 503 status on failure

**Breaking Change**: YES (response format changes)  
**Migration**: Update monitoring tools

---

### L-19: Graceful Shutdown Handling

**Current**: Immediate shutdown on SIGTERM  
**Improvement**: Drain connections gracefully

**Implementation**:
```python
import signal
import asyncio

shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    logger.info("Received shutdown signal, draining connections...")
    shutdown_event.set()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global http_client
    http_client = httpx.AsyncClient(...)
    
    yield
    
    # Shutdown - wait for in-flight requests
    logger.info("Waiting for in-flight requests to complete...")
    await asyncio.sleep(2)  # Grace period
    await http_client.aclose()
    logger.info("Shutdown complete")
```

**Tests**:
- Send SIGTERM during active request
- Verify request completes before shutdown

**Breaking Change**: NO  
**Migration**: N/A

---

### L-20: Configuration Validation on Startup

**Current**: Config loaded without validation  
**Improvement**: Validate all routes on startup

**Implementation**:
```python
def validate_config_on_startup() -> dict[str, list[str]]:
    """Validate all routes in config
    
    Returns:
        Dictionary with 'errors' and 'warnings' lists
    """
    results = {"errors": [], "warnings": []}
    routes = Config().load()
    
    for name, target in routes.items():
        # Validate route name
        is_valid, error = validate_route_name(name)
        if not is_valid:
            results['errors'].append(f"Route '{name}': {error}")
        
        # Validate target
        parsed = parse_target(str(target))
        if not parsed:
            results['errors'].append(f"Route '{name}': invalid target {target}")
    
    return results
```

**Tests**:
- Load config with invalid routes
- Verify errors logged on startup

**Breaking Change**: NO (warnings only)  
**Migration**: N/A

---

## Priority 5: Documentation and Tooling

### L-21: Security Configuration Documentation

**Current**: Security features scattered across docs  
**Improvement**: Centralized security guide

**File**: `docs/SECURITY.md`

**Contents**:
- Environment variables summary table
- Security defaults and how to override
- Certificate management guide
- SSRF protection configuration
- Security headers configuration
- Audit recommendations and compliance

**Example**:
```markdown
## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVHOST_ALLOW_PRIVATE_NETWORKS` | `0` | Allow proxying to private IPs |
| `DEVHOST_VERIFY_CERTS` | `1` | Verify SSL certificates |
| `DEVHOST_SECURITY_HEADERS` | `0` | Add security headers (opt-in) |
| `DEVHOST_LOG_REQUESTS` | `0` | Log all requests (may leak secrets) |
```

---

### L-22: Migration Guide for v3.0

**File**: `docs/MIGRATION-v3.md`

**Contents**:
- Breaking changes from v2.x
- New security features and defaults
- Environment variable changes
- State file format changes
- Upgrade procedure

---

### L-23: Security Audit Summary

**File**: `docs/SECURITY-AUDIT-SUMMARY.md`

**Contents**:
- Phases 1-4 summary
- Vulnerabilities found and fixed
- Test coverage statistics
- Remaining recommendations
- Compliance notes (SOC2, ISO 27001 considerations)

---

## Implementation Timeline

### Week 1 (Feb 12-18, 2026):
- ✅ L-11: Executable path validation
- ✅ L-12: Subprocess timeouts
- ✅ L-13: Input length limits
- ✅ L-20: Config validation on startup

### Week 2 (Feb 19-25, 2026):
- ✅ L-14: Connection pooling optimization
- ✅ L-15: Route lookup optimization
- ✅ L-18: Health check enhancements
- ✅ L-19: Graceful shutdown

### Week 3 (Feb 26 - Mar 4, 2026):
- ✅ L-16: Structured logging
- ✅ L-17: Metrics enhancements
- ✅ L-21: Security documentation
- ✅ L-22: Migration guide
- ✅ L-23: Audit summary

---

## Success Metrics

**Security**:
- [ ] 100% of subprocess calls have timeouts
- [ ] 100% of executables validated before use
- [ ] 100% of inputs have length limits
- [ ] 0 high/critical vulnerabilities in final audit

**Performance**:
- [ ] 20% reduction in p95 latency (route lookup caching)
- [ ] 2x increase in max concurrent connections (pooling)
- [ ] 100% uptime during graceful shutdown tests

**Observability**:
- [ ] Structured logging available
- [ ] 10+ metrics exposed on `/metrics`
- [ ] Health check covers 5+ subsystems

**Documentation**:
- [ ] SECURITY.md complete with all env vars
- [ ] MIGRATION-v3.md covers all breaking changes
- [ ] SECURITY-AUDIT-SUMMARY.md covers Phases 1-4

---

## Risk Assessment

### L-11 (Executable Validation)
- **Risk**: May break existing setups with custom executable paths
- **Mitigation**: Warning-only mode initially, errors in v3.1

### L-18 (Health Check Changes)
- **Risk**: Breaking change for monitoring tools
- **Mitigation**: Provide `/health/simple` legacy endpoint

### L-19 (Graceful Shutdown)
- **Risk**: May delay shutdown in edge cases
- **Mitigation**: Hard timeout after 30 seconds

---

## Post-Phase 4 Considerations

**v3.0 Release Candidates**:
- RC1: After L-11 to L-13 (security hardening)
- RC2: After L-14 to L-19 (performance + production)
- RC3: After L-21 to L-23 (documentation)

**v3.0 GA**: Target March 7, 2026

**Future Enhancements** (v3.1+):
- Rate limiting per route (optional)
- Request throttling
- Circuit breaker pattern for failing upstreams
- Prometheus metrics exporter
- Distributed tracing (OpenTelemetry)
- mTLS support for upstream connections

---

## Dependencies

**Required**:
- Phase 3 completion ✅
- All security tests passing ✅
- CI/CD pipeline stable ✅

**Optional**:
- Load testing infrastructure (locust, hey)
- Monitoring stack (Prometheus, Grafana)
- Log aggregation (ELK, Loki)

---

## Breaking Changes Summary

**Minimal Breaking Changes** (opt-in approach):
- L-18: Health check response format (provide legacy endpoint)
- All other changes are additive or opt-in

**Migration Path**:
1. Upgrade to v3.0-RC1
2. Test with existing configuration
3. Enable new features gradually via environment variables
4. Update monitoring to use new health check format
5. Upgrade to v3.0 GA

---

## Notes

- Phase 4 prioritizes production readiness over new features
- All security recommendations from INPUT-SANITIZATION-AUDIT.md addressed
- Performance improvements are measurable and testable
- Documentation completes the security story for compliance audits
- Graceful degradation approach: warnings before errors

**Phase 4 Goal**: Production-ready v3.0 release with comprehensive security hardening
