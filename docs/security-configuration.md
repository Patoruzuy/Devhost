# Security Configuration

Devhost v3.0 implements defense-in-depth security measures to protect against common web application vulnerabilities. This document describes the security features, configuration options, and migration guidance.

## Security Features

### SSRF Protection (C-01)

**Threat**: Server-Side Request Forgery attacks where malicious routes could target internal cloud metadata endpoints or private network services.

**Protection**:
- Blocks access to AWS EC2 metadata (169.254.169.254)
- Blocks access to GCP metadata (metadata.google.internal)
- Blocks access to Azure metadata (169.254.169.253)
- Blocks all private IP ranges (10.0.0.0/8, 192.168.0.0/16, 172.16.0.0/12)
- Blocks link-local addresses (169.254.0.0/16)

**Configuration**:
```bash
# Allow private networks (local development only)
export DEVHOST_ALLOW_PRIVATE_NETWORKS=1
```

### URL Scheme Validation (H-01)

**Threat**: Protocol smuggling attacks using file://, ftp://, or other dangerous URL schemes.

**Protection**:
- Only allows http:// and https:// schemes
- Rejects file://, ftp://, gopher://, data:, javascript: schemes
- Logs rejected schemes at WARNING level

### Host Header Injection Prevention (H-02)

**Threat**: HTTP header injection attacks via control characters in Host headers.

**Protection**:
- Validates hostnames against RFC 1123 requirements
- Blocks control characters (\r, \n, \x00)
- Enforces length limits (63 chars per label, 253 total)
- Prevents header smuggling attacks

### Privilege Escalation Prevention (H-03)

**Threat**: Unauthorized modification of Windows hosts file.

**Protection** (Windows only):
- Requires administrator privileges for hosts file operations
- Validates hostname format before modification
- Prompts for confirmation on destructive operations
- Creates backups before all modifications
- Logs all operations for audit trails

## Environment Variables

### DEVHOST_ALLOW_PRIVATE_NETWORKS

**Default**: alse (disabled)  
**Impact**: HIGH - Disables SSRF protection  
**Use Case**: Enable proxying to private IPs (192.168.x.x, 10.x.x.x, 172.16-31.x.x) for local development

**Example**:
```bash
# Temporary (current session)
export DEVHOST_ALLOW_PRIVATE_NETWORKS=1

# Permanent (Linux/macOS - add to ~/.bashrc or ~/.zshrc)
echo 'export DEVHOST_ALLOW_PRIVATE_NETWORKS=1' >> ~/.bashrc

# Permanent (Windows - add to PowerShell profile)
echo '\=1' >> \C:\Users\soyse.TIBURON\OneDrive\Documents\PowerShell\Microsoft.PowerShell_profile.ps1
```

**Security Warning**: ⚠️ Never enable this in production environments. Only use for local development when you need to proxy to devices on your LAN.

### DEVHOST_TIMEOUT

**Default**: 60 (seconds)  
**Impact**: MEDIUM - Request timeout  
**Valid Range**: 5-300 seconds

**Example**:
```bash
export DEVHOST_TIMEOUT=120  # 2 minutes for slow backends
```

### DEVHOST_RETRY_ATTEMPTS

**Default**: 3  
**Impact**: LOW - Connection retry attempts  
**Valid Range**: 1-10

**Example**:
```bash
export DEVHOST_RETRY_ATTEMPTS=5  # More retries for unstable backends
```

### DEVHOST_LOG_REQUESTS

**Default**: alse  
**Impact**: LOW - Enable per-request logging  

**Example**:
```bash
export DEVHOST_LOG_REQUESTS=1  # Enable detailed request logging
```

## Migration Guide

### Breaking Change: Private Network Blocking

**Effective**: v3.0.0  
**Impact**: Existing configurations using 192.168.x.x or 10.x.x.x upstream targets will be blocked

#### Error Message

When a private network target is blocked, you'll see:

```
Security policy blocked this request: Target 192.168.1.100 resolves to private IP (SSRF protection).
Use DEVHOST_ALLOW_PRIVATE_NETWORKS=1 to override for local development.
```

#### Migration Steps

**Option 1: Enable Private Network Access (Recommended for Development)**

```bash
# Set environment variable
export DEVHOST_ALLOW_PRIVATE_NETWORKS=1

# Restart devhost
devhost proxy restart
```

**Option 2: Use Localhost Targets (Preferred)**

If your service runs on the same machine, use localhost instead:

```bash
# Before (blocked)
devhost add myapp 192.168.1.100:8000

# After (allowed)
devhost add myapp localhost:8000
# or
devhost add myapp 127.0.0.1:8000
```

**Option 3: Port Forwarding (For Remote Services)**

Use SSH port forwarding to access remote services via localhost:

```bash
# Forward remote port to localhost
ssh -L 8000:192.168.1.100:8000 user@gateway

# Then add localhost route
devhost add myapp localhost:8000
```

### Breaking Change: URL Scheme Restriction

**Effective**: v3.0.0  
**Impact**: Routes using file://, ftp://, or other non-HTTP schemes will be rejected

#### Migration Steps

Only http:// and https:// schemes are allowed. Update your routes:

```bash
# Before (rejected)
devhost add files file:///var/www/files

# After (use proper HTTP server)
# Start HTTP server: python -m http.server 8080 --directory /var/www/files
devhost add files localhost:8080
```

## Security Best Practices

### For Local Development

1. **Use localhost by default**: Always bind apps to 127.0.0.1, not 0.0.0.0
2. **Enable private networks only when needed**: Set DEVHOST_ALLOW_PRIVATE_NETWORKS=1 only for specific development scenarios
3. **Use System Mode sparingly**: Gateway Mode (port 7777) is safer as it doesn't require admin privileges
4. **Monitor logs**: Enable DEVHOST_LOG_REQUESTS=1 when debugging security issues

### For Windows Users

1. **Run as standard user**: Use Gateway Mode (default) which doesn't require admin privileges
2. **Review hosts file changes**: Check C:\Windows\System32\drivers\etc\hosts.bak for backups before modifications
3. **Use PowerShell elevation carefully**: Only elevate when explicitly switching to System Mode

### Incident Response

If you suspect a security issue:

1. **Stop the router**: devhost proxy stop
2. **Review logs**: Check ~/.devhost/router.log or %TEMP%\devhost-router.log
3. **Restore hosts file** (Windows): devhost hosts restore or manually restore from hosts.bak
4. **Report**: Email security@devhost.dev or create a private security advisory on GitHub

## Security Audit Trail

All security-relevant operations are logged:

- **SSRF blocks**: Logged at WARNING level with target IP
- **Invalid hostnames**: Logged at WARNING level with reason
- **Rejected schemes**: Logged at WARNING level
- **Hosts file modifications** (Windows): Logged at INFO level with hostname

View logs:
```bash
# Show recent logs
devhost logs

# Follow logs in real-time
devhost logs -f

# Show last 100 lines
devhost logs -n 100
```

## Reporting Security Vulnerabilities

**Do not** report security vulnerabilities through public GitHub issues.

**Do** send details to: security@devhost.dev

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We aim to respond within 48 hours and provide fixes within 7 days for critical vulnerabilities.
