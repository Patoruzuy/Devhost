# Input Sanitization Audit (L-10)

**Status**: COMPLETE  
**Date**: 2026-02-05  
**Scope**: All subprocess calls and user input validation in devhost_cli/  

---

## Executive Summary

Audited all subprocess calls and user input handling across the Devhost CLI codebase. **No critical shell injection vulnerabilities found**. All subprocess calls use list-based arguments (no `shell=True`), and user inputs are properly validated before use.

**Key Findings**:
- ✅ No `os.system()` with user input (1 use found: ANSI escape enabler, no user input)
- ✅ No `shell=True` in subprocess calls
- ✅ All subprocess calls use list-based arguments (safe from shell injection)
- ✅ User inputs (names, URLs, ports) validated before use
- ✅ File paths use `Path` objects (safer than string concatenation)

---

## Audit Results by File

### 1. `devhost_cli/router_manager.py`

**subprocess calls**: 1  
**Risk level**: ✅ LOW  

```python
# Line 147 - Router process launch
process = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", factory_flag, ...]
)
```

**Input sources**:
- `sys.executable` - Python interpreter (system-provided)
- `factory_flag` - hardcoded string
- `port` - integer from config (validated)

**Verdict**: SAFE - all arguments are controlled, no user input directly used

---

### 2. `devhost_cli/main.py`

**subprocess calls**: 1  
**Risk level**: ✅ LOW  

```python
# Line 502 - Browser open command
result = subprocess.run(cmd, check=False)
# cmd is from webbrowser.get().open() - vetted by Python stdlib
```

**Verdict**: SAFE - uses Python's `webbrowser` module (handles escaping)

---

### 3. `devhost_cli/caddy_lifecycle.py`

**subprocess calls**: 12  
**Risk level**: ✅ LOW  

**Patterns**:
```python
# Line 95 - Caddy validate
subprocess.run([caddy_exe, "validate", "--config", str(config_path)])

# Line 116 - Caddy start
subprocess.run([caddy_exe, "start", "--config", str(config_path)])

# Line 126 - Process check (ps command)
subprocess.run(["ps", "-p", str(pid), "-o", "comm="])
```

**Input sources**:
- `caddy_exe` - executable path from system PATH or config
- `config_path` - Path object (validated exists before use)
- `pid` - integer from process tracking

**Potential risk**: Executable path (`caddy_exe`) could be manipulated via environment
**Mitigation**: Always validate executable exists and is not user-controllable

**Verdict**: SAFE - list-based args, Path objects used, PIDs are integers

---

### 4. `devhost_cli/certificates.py`

**subprocess calls**: 1  
**Risk level**: ✅ LOW  

```python
# Line 128 - OpenSSL certificate check
subprocess.run(
    ['openssl', 'x509', '-in', str(cert_path), '-noout', '-enddate'],
    ...
)
```

**Input sources**:
- `cert_path` - Path object (validated exists before use)

**Verdict**: SAFE - Path object, no shell injection possible

---

### 5. `devhost_cli/windows.py`

**subprocess calls**: 9  
**Risk level**: ⚠️ MEDIUM (DNS/hosts file operations)

**Patterns**:
```python
# Line 347 - Check admin with Win32 API
subprocess.run(["net", "session"], ...)

# Line 383 - Get DNS cache
subprocess.run(["ipconfig", "/displaydns"], ...)

# Line 411 - Start Caddy
subprocess.run([exe, "start", "--config", str(user_caddy)], ...)
```

**Input sources**:
- `exe` - Caddy executable path
- `user_caddy` - Path object to config file
- DNS names and IPs validated in `validation.py`

**Potential risks**:
1. Admin privilege checks could be bypassed on non-Windows
2. DNS names in hosts file could contain control characters

**Mitigations**:
- Platform checks (`IS_WINDOWS`) prevent cross-platform issues
- Hostname validation in `validation.py` blocks control characters
- File paths use Path objects

**Verdict**: SAFE with existing validation - hostname validation prevents injection

---

### 6. `devhost_cli/utils.py`

**os.system calls**: 1  
**Risk level**: ✅ LOW  

```python
# Line 30 - Enable ANSI escape codes on Windows
os.system("")  # Empty string - safe, no user input
```

**Verdict**: SAFE - no user input, Windows-only ANSI enabler

---

### 7. `devhost_cli/tunnel.py`

**subprocess calls**: 6  
**Risk level**: ✅ LOW  

**Patterns**:
```python
# Line 266 - Cloudflared tunnel
subprocess.Popen(
    [exe, "tunnel", "--url", target_url, ...],
    ...
)

# Line 296 - Ngrok tunnel
subprocess.Popen(
    [exe, "http", str(port), ...],
    ...
)
```

**Input sources**:
- `exe` - Tunnel executable path (cloudflared, ngrok, localtunnel)
- `target_url` - constructed from validated port/hostname
- `port` - integer from config

**Verdict**: SAFE - list-based args, validated inputs

---

## Validation Mechanisms

### Hostname Validation (`devhost_cli/validation.py`)

```python
def validate_hostname(hostname: str) -> tuple[bool, str | None]:
    """Blocks control characters, relative paths, etc."""
    # Prevents header injection
    if any(char in hostname for char in ["\r", "\n", "\x00"]):
        return (False, "Invalid hostname: contains control characters")
    
    # Prevents path traversal
    if ".." in hostname or hostname.startswith("/"):
        return (False, "Invalid hostname: path-like string")
```

✅ Protects against header injection and path traversal

### Port Validation

```python
def parse_target(value: str) -> tuple[str, str, int] | None:
    """Validates port ranges, schemes, formats"""
    # Ensures port is 1-65535
    if not (1 <= port <= 65535):
        return None
```

✅ Prevents port number exploits

### URL Scheme Validation

```python
def parse_target(value: str) -> tuple[str, str, int] | None:
    """Only allows http:// and https://"""
    if scheme not in ("http", "https"):
        return None
```

✅ Prevents `file://`, `ftp://`, etc. scheme injection

---

## Recommendations

### 1. Executable Path Validation (MEDIUM Priority)

**Current state**: Executable paths for `caddy`, `cloudflared`, `ngrok` are taken from PATH or config

**Recommendation**: Add explicit validation:

```python
def validate_executable(exe_path: str) -> bool:
    """Validate executable is safe to run"""
    path = Path(exe_path)
    
    # Must exist
    if not path.exists():
        return False
    
    # Must be executable
    if not os.access(path, os.X_OK):
        return False
    
    # Should not be in user-writable locations (on Windows)
    if IS_WINDOWS:
        user_dirs = [Path.home(), Path.cwd()]
        if any(str(path).startswith(str(d)) for d in user_dirs):
            logger.warning(f"Executable {path} is in user-writable location")
    
    return True
```

**Impact**: Prevents execution of malicious executables from untrusted locations

---

### 2. Timeout Enforcement (LOW Priority)

**Current state**: Subprocess calls in `certificates.py` have `timeout=5`

**Recommendation**: Add timeouts to all subprocess calls:

```python
subprocess.run(
    [...],
    timeout=30,  # Prevent indefinite hangs
    check=False
)
```

**Impact**: Prevents DoS via hanging subprocesses

---

### 3. Input Length Limits (LOW Priority)

**Current state**: No explicit length limits on hostnames, route names

**Recommendation**: Add maximum length checks:

```python
MAX_HOSTNAME_LENGTH = 253  # RFC 1035
MAX_ROUTE_NAME_LENGTH = 63  # DNS label limit

def validate_hostname(hostname: str) -> tuple[bool, str | None]:
    if len(hostname) > MAX_HOSTNAME_LENGTH:
        return (False, f"Hostname too long (max {MAX_HOSTNAME_LENGTH} chars)")
    ...
```

**Impact**: Prevents buffer overflow-like issues in downstream systems

---

## Security Posture Summary

| Category | Status | Risk | Notes |
|----------|--------|------|-------|
| Shell injection | ✅ SAFE | LOW | No `shell=True`, list-based args |
| Command injection | ✅ SAFE | LOW | No user input in subprocess commands |
| Path traversal | ✅ SAFE | LOW | Path objects used, `..` blocked |
| Header injection | ✅ SAFE | LOW | Control characters blocked |
| Executable validation | ⚠️ IMPROVE | MEDIUM | Add explicit exe path validation |
| Timeout enforcement | ⚠️ IMPROVE | LOW | Add timeouts to all subprocess calls |
| Input length limits | ⚠️ IMPROVE | LOW | Add max length checks |

---

## Test Coverage

**Existing tests**:
- ✅ `tests/test_security_ssrf.py` - URL/hostname validation
- ✅ `tests/test_security_headers.py` - Header validation
- ✅ `tests/test_security_schemes.py` - Scheme validation
- ✅ `tests/test_validation.py` - Input parsing and validation

**No tests needed**: Subprocess calls are safe by design (list-based args)

---

## Conclusion

**Overall verdict**: ✅ **LOW RISK**

The codebase demonstrates good security practices:
- All subprocess calls use list-based arguments (immune to shell injection)
- User inputs validated before use (hostnames, ports, URLs)
- Path objects used instead of string concatenation
- Control characters blocked in hostnames
- URL schemes restricted to http/https

**Recommendations for future hardening**:
1. Add executable path validation (medium priority)
2. Add timeouts to all subprocess calls (low priority)
3. Add input length limits (low priority)

**No critical vulnerabilities found** - code is production-ready from an input sanitization perspective.
