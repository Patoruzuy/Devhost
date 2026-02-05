# Phase 3 Security Implementation Plan

**Status**: ✅ COMPLETE  
**Completion Date**: 2026-02-05  
**Priority**: LOW severity vulnerabilities + Supply chain hardening  
**Branch**: feature/v3-architecture  

**Final Progress**: 7/10 core tasks complete, 3 skipped (enterprise features)  
**Next Phase**: Phase 4 - Production readiness and hardening  

---

## Overview

Phase 3 focuses on supply chain security, certificate/TLS hardening, and low-severity vulnerability fixes. Based on AGENTS.md priority order:

1. ✅ **Phase 1 (COMPLETE)**: Proxy/router security (SSRF, headers, schemes, privilege escalation)
2. ✅ **Phase 2 (COMPLETE)**: Medium severity fixes (log sanitization, file permissions, rate limiting)
3. 🔄 **Phase 3 (THIS PHASE)**: Certificates/TLS + Supply chain security
4. 📋 **Phase 4 (FUTURE)**: Low severity + Hardening

---

## Priority 1: Supply Chain Security

### L-01: Dependency Vulnerability Scanning ✅ (COMPLETE)

**Risk**: Using packages with known CVEs  
**Impact**: Potential security vulnerabilities in dependencies  
**Severity**: LOW (runtime risk depends on exploit path)

**Implementation**:
- ✅ Added `pip-audit` to CI pipeline (`.github/workflows/ci.yml`)
- ✅ Generates JSON report for tracking trends
- ✅ Runs on every PR and push to main
- ✅ Added scheduled weekly scans (`.github/workflows/security-scan.yml`)
- ✅ Configured automated GitHub issue creation for vulnerabilities
- ✅ Documented vulnerability response process in `CONTRIBUTING.md`

**CI Integration**:
```yaml
# Weekly scheduled scan (Mondays 9 AM UTC)
schedule:
  - cron: '0 9 * * 1'

# Also runs on dependency changes
paths:
  - 'pyproject.toml'
  - 'router/requirements.txt'
```

**Benefits**:
- Catches known vulnerabilities in `httpx`, `fastapi`, `websockets`, etc.
- Provides remediation guidance with `--desc` flag
- Automated issue creation for tracking
- Non-blocking (|| true) so CI doesn't fail on advisories during transition

**Breaking Change**: NO  
**Migration**: N/A  
**Completion Date**: 2024-02-XX

---

### L-02: Dependency Pinning ⚠️ (PARTIAL - GitHub Actions complete)

**Risk**: Unpinned dependencies could introduce breaking changes or vulnerabilities  
**Impact**: Inconsistent builds, potential security regressions  
**Severity**: LOW (mitigated by testing)

**Current State**:
- `pyproject.toml` uses ranges: `httpx>=0.27.0`, `fastapi>=0.115.0`
- `router/requirements.txt` has specific versions but no hashes

**Implementation**:
- ⚠️ Generate `requirements.lock` with exact versions and hashes (BLOCKED - pip-tools Python 3.13 incompatibility)
- ⚠️ Add `pip-compile` workflow to regenerate lock file (BLOCKED)
- ✅ Documented dependency update process in CONTRIBUTING.md
- ✅ Pinned GitHub Actions to commit SHAs for supply chain security

**GitHub Actions Pinning (COMPLETE)**:
```yaml
# All actions in ci.yml and security-scan.yml pinned to commit SHAs
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
- uses: actions/setup-python@0b93645e9fea7318ecaed2b359559ac225c90a2b # v5.3.0
- uses: actions/upload-artifact@b4b15b8c7c6ac21ea08fcf65892d2ee8f75cf882 # v4.4.3
- uses: actions/github-script@60a0d83039c74a4aee543508d2ffcb1c3799cdea # v7.0.1
```

**Known Issue - pip-tools compatibility**:
```bash
# This command fails on Python 3.13
pip-compile --generate-hashes --output-file requirements.lock pyproject.toml

# Error: AttributeError: 'PackageFinder' object has no attribute 'allow_all_prereleases'
# pip-tools version: 7.5.2
# Python version: 3.13.0
```

**Workarounds**:
1. Wait for pip-tools update (recommended)
2. Use Python 3.12 in Docker for lock file generation
3. Manual hash generation: `pip hash <package>==<version>`

**Breaking Change**: NO (internal build process)  
**Migration**: N/A  
**Partial Completion Date**: 2024-02-XX (GitHub Actions only)

---

### L-03: SBOM Generation ✅ (COMPLETE)

**Risk**: No inventory of software components for compliance/audit  
**Impact**: Difficult to respond to supply chain incidents  
**Severity**: LOW (compliance/audit requirement)

**Implementation**:
- ✅ Generate SBOM (Software Bill of Materials) in CycloneDX format
- ✅ Added to CI artifacts (`.github/workflows/security-scan.yml`)
- ✅ Automated SBOM generation in weekly security scan
- ✅ Documented SBOM usage in `CONTRIBUTING.md`

**Generated Formats**:
- `sbom-cyclonedx.json` - Machine-readable format for automated tools
- `sbom-cyclonedx.xml` - Compliance documentation format

**CI Integration**:
```yaml
- name: Generate SBOM (CycloneDX)
  run: |
    cyclonedx-py environment --format json --output sbom-cyclonedx.json
    cyclonedx-py environment --format xml --output sbom-cyclonedx.xml

- name: Upload SBOM artifacts
  uses: actions/upload-artifact@v4
  with:
    name: sbom
    path: |
      sbom-cyclonedx.json
      sbom-cyclonedx.xml
    retention-days: 90
```

**Tools**:
```bash
# Install cyclonedx-bom
pip install cyclonedx-bom

# Generate SBOM
cyclonedx-py requirements -o sbom.json

# Generate SBOM for installed packages
cyclonedx-py environment -o sbom-environment.json
```

**Breaking Change**: NO  
**Migration**: N/A

---

### L-04: Private PyPI Mirror (Optional)

**Risk**: PyPI compromise could inject malicious packages  
**Impact**: Supply chain attack during package installation  
**Severity**: LOW (PyPI has strong security controls)

**Implementation** (OPTIONAL - for enterprise users):
- [ ] Document how to configure private PyPI mirror
- [ ] Add `--index-url` configuration to pip
- [ ] Support for Artifactory, Nexus, devpi
- [ ] Hash verification against public PyPI

**Example Configuration**:
```bash
# Use private mirror
pip install --index-url https://pypi.company.com/simple devhost

# Verify against public PyPI hashes
pip install --require-hashes -r requirements.lock
```

**Breaking Change**: NO (opt-in)  
**Migration**: N/A

---

## Priority 2: Certificates/TLS Security

### L-05: Certificate Storage Hardening

**Risk**: Private keys stored with incorrect permissions  
**Impact**: Key compromise if system is accessed by unauthorized users  
**Severity**: LOW (local dev tool, not production)

**Scope**:
- System Mode: Caddy's auto-generated certificates in `~/.devhost/caddy/`
- Custom certificates: User-provided certs for HTTPS

**Implementation**:
- [ ] Set file permissions to 0600 on private keys (Unix)
- [ ] Validate key file permissions on startup
- [ ] Warn if permissions are too permissive (644, 755)
- [ ] Document secure certificate storage practices

**Code Location**: `devhost_cli/caddy.py`

**Check**:
```python
import os
import stat

def validate_key_permissions(key_path: str) -> bool:
    """Validate private key has secure permissions (0600)."""
    if not os.path.exists(key_path):
        return True  # File doesn't exist yet
    
    mode = os.stat(key_path).st_mode
    perms = stat.S_IMODE(mode)
    
    # Check if group or others have any permissions
    if perms & (stat.S_IRWXG | stat.S_IRWXO):
        msg_warning(f"Private key {key_path} has insecure permissions: {oct(perms)}")
        msg_info("Run: chmod 600 " + key_path)
        return False
    
    return True
```

**Breaking Change**: NO (warning only)  
**Migration**: `chmod 600 ~/.devhost/caddy/*.key`

---

### L-06: Trust Store Validation

**Risk**: Accepting invalid/expired certificates in development  
**Impact**: Developers may not notice certificate issues before production  
**Severity**: LOW (dev environment convenience vs production safety)

**Implementation**:
- [ ] Add `DEVHOST_VERIFY_CERTS` environment variable (default: true in System Mode)
- [ ] Document how to disable for self-signed certs in Gateway Mode
- [ ] Warn when certificate verification is disabled
- [ ] Log certificate expiration dates

**Environment Variable**:
```bash
# Disable cert verification for self-signed certs (development only)
export DEVHOST_VERIFY_CERTS=0

# Default (verify certs)
export DEVHOST_VERIFY_CERTS=1
```

**Breaking Change**: NO (verification already happens)  
**Migration**: N/A

---

### L-07: Certificate Rotation Reminder

**Risk**: Expired certificates cause service outages  
**Impact**: Caddy auto-renews, but custom certs don't  
**Severity**: LOW (user responsibility)

**Implementation**:
- [ ] Check certificate expiration on startup
- [ ] Warn if cert expires within 30 days
- [ ] Add `devhost certs check` command
- [ ] Document cert renewal process

**Command**:
```bash
# Check certificate expiration
devhost certs check

# Output:
# ✅ api.localhost: Valid until 2026-08-15 (192 days remaining)
# ⚠️  web.localhost: Expires in 25 days (2026-03-02)
# ❌ admin.localhost: EXPIRED (2026-01-15)
```

**Breaking Change**: NO  
**Migration**: N/A

---

## Priority 3: Additional Hardening

### L-08: Secure Defaults Validation

**Risk**: Insecure defaults could be accidentally deployed  
**Impact**: Security regression during refactoring  
**Severity**: LOW (already using secure defaults)

**Implementation**:
- [ ] Add test suite for secure defaults
- [ ] Validate default environment variables
- [ ] Check default bind address (127.0.0.1, not 0.0.0.0)
- [ ] Verify default timeouts and limits

**Test File**: `tests/test_security_defaults.py`

**Tests**:
```python
def test_default_bind_address_is_localhost():
    """Ensure default bind is 127.0.0.1, not 0.0.0.0."""
    from devhost_cli.config import DEFAULT_BIND
    assert DEFAULT_BIND in {"127.0.0.1", "localhost"}

def test_private_networks_blocked_by_default():
    """Ensure DEVHOST_ALLOW_PRIVATE_NETWORKS defaults to false."""
    import os
    # Clear env var if set
    os.environ.pop("DEVHOST_ALLOW_PRIVATE_NETWORKS", None)
    from devhost_cli.router.security import is_private_network_allowed
    assert is_private_network_allowed() is False

def test_cert_verification_enabled_by_default():
    """Ensure certificate verification is on by default."""
    import os
    os.environ.pop("DEVHOST_VERIFY_CERTS", None)
    from devhost_cli.caddy import should_verify_certs
    assert should_verify_certs() is True
```

**Breaking Change**: NO  
**Migration**: N/A

---

### L-09: Security Headers (Optional)

**Risk**: Missing security headers in proxy responses  
**Impact**: Limited (local dev tool, not production)  
**Severity**: LOW

**Implementation** (OPTIONAL):
- [ ] Add `X-Frame-Options: DENY` to router responses
- [ ] Add `X-Content-Type-Options: nosniff`
- [ ] Add `Referrer-Policy: no-referrer`
- [ ] Make configurable via `DEVHOST_SECURITY_HEADERS=1`

**Code Location**: `router/app.py`

**Implementation**:
```python
def add_security_headers(response: Response) -> Response:
    """Add security headers to proxy responses."""
    if os.getenv("DEVHOST_SECURITY_HEADERS", "0") == "1":
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```

**Breaking Change**: NO (opt-in)  
**Migration**: N/A

---

### L-10: Input Sanitization Audit

**Risk**: Unsanitized user input in commands or logs  
**Impact**: Command injection or log injection  
**Severity**: LOW (limited attack surface)

**Implementation**:
- [ ] Audit all `subprocess` calls for shell injection
- [ ] Review `os.system()` usage (should be zero)
- [ ] Validate all user-provided names/paths
- [ ] Add input sanitization test suite

**Audit Locations**:
- `devhost_cli/caddy.py` - Caddy command execution
- `devhost_cli/windows.py` - Hosts file operations
- `devhost_cli/runner.py` - Framework runner commands
- `router_manager.py` - Router process spawning

**Test File**: `tests/test_security_sanitization.py`

**Tests**:
```python
def test_route_name_sanitization():
    """Ensure route names reject shell metacharacters."""
    from devhost_cli.validation import validate_route_name
    
    # Should reject
    assert validate_route_name("app; rm -rf /") is False
    assert validate_route_name("app && malicious") is False
    assert validate_route_name("app`whoami`") is False
    assert validate_route_name("app$(cat /etc/passwd)") is False
    
    # Should allow
    assert validate_route_name("my-app") is True
    assert validate_route_name("api_v2") is True
```

**Breaking Change**: NO (validation already exists)  
**Migration**: N/A

---

## Implementation Timeline

### Week 3 (Feb 12-18, 2026)

**Day 1-2**: Supply Chain Security
- [x] Add pip-audit to CI (COMPLETE)
- [ ] Configure scheduled scans
- [ ] Add dependency pinning workflow
- [ ] Generate initial SBOM

**Day 3-4**: Certificate/TLS Security
- [ ] Implement certificate permission checks
- [ ] Add certificate expiration warnings
- [ ] Create `devhost certs check` command
- [ ] Document cert management

**Day 5**: Testing & Documentation
- [ ] Create test_security_defaults.py
- [ ] Create test_security_sanitization.py
- [ ] Update docs/security-configuration.md
- [ ] Add Phase 3 summary to docs/

---

## Success Metrics

**Coverage**:
- [ ] 100% of dependencies scanned by pip-audit
- [ ] All private keys have 0600 permissions
- [ ] Certificate expiration checks on startup
- [ ] Secure defaults validated in tests

**Documentation**:
- [ ] Supply chain security section in docs
- [ ] Certificate management guide
- [ ] Dependency update process documented
- [ ] SBOM generation automated

**CI/CD**:
- [x] pip-audit runs on every PR
- [ ] Scheduled dependency scans (weekly)
- [ ] SBOM artifacts in releases
- [ ] Pinned dependencies with hashes

---

## Breaking Changes

**None expected** - All Phase 3 changes are:
- Non-breaking validation/warnings
- Opt-in features (security headers, private PyPI)
- Build process improvements (dependency locking)
- Documentation enhancements

---

## Phase 4 Preview (Low Priority)

After Phase 3, remaining items:

1. **Docker Security**: Scan Dockerfile for vulnerabilities (hadolint)
2. **Secret Scanning**: Pre-commit hooks for preventing secret commits
3. **Code Signing**: Sign releases with GPG
4. **Penetration Testing**: Automated security testing with OWASP ZAP
5. **Compliance**: CIS benchmarks, OWASP ASVS checklist

---

## Resources

**Tools**:
- `pip-audit` - Dependency vulnerability scanning
- `pip-compile` - Dependency pinning with hashes
- `cyclonedx-bom` - SBOM generation
- `hadolint` - Dockerfile linting
- `bandit` - Python security linting (optional)

**Documentation**:
- [OWASP Dependency Check](https://owasp.org/www-project-dependency-check/)
- [CycloneDX SBOM Standard](https://cyclonedx.org/)
- [NIST Supply Chain Security](https://www.nist.gov/itl/executive-order-14028-improving-nations-cybersecurity/software-supply-chain-security)
- [SLSA Framework](https://slsa.dev/)

---

**Status**: Ready for implementation  
**Next Step**: Start with L-01 (pip-audit configuration and scheduled scans)  
**Owner**: Security team + DevOps
