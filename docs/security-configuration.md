# Security Guide

Devhost implements defense-in-depth security measures to protect against common web application vulnerabilities while maintaining ease of use for local development.

## Security Model

**Core Principle**: Secure by default, with explicit opt-ins for permissive behavior.

- **Localhost-only binding**: Router binds to 127.0.0.1 by default (not 0.0.0.0)
- **No LAN exposure**: Apps are not exposed to your network unless you explicitly tunnel
- **SSRF protection**: Blocks access to cloud metadata endpoints and private networks
- **Input validation**: All user inputs are validated before use
- **Subprocess safety**: All subprocess calls use list-based arguments (no shell injection)
- **Certificate verification**: TLS certificates are verified by default

## Network Security

### SSRF (Server-Side Request Forgery) Protection

Devhost protects against SSRF attacks that could target internal infrastructure:

**Blocked by default**:
- Cloud metadata endpoints:
  - AWS: `169.254.169.254`
  - GCP: `metadata.google.internal`
  - Azure: `169.254.169.253`
- Private IP ranges:
  - `10.0.0.0/8` (Class A private)
  - `172.16.0.0/12` (Class B private)
  - `192.168.0.0/16` (Class C private)
  - `169.254.0.0/16` (Link-local addresses)

**Allow private networks for local development**:
```bash
export DEVHOST_ALLOW_PRIVATE_NETWORKS=1
devhost start
```

⚠️ **Warning**: Only enable this for local development. Never use in production environments.

### URL Scheme Validation

Only HTTP and HTTPS protocols are allowed to prevent protocol smuggling attacks.

**Allowed schemes**:
- `http://`
- `https://`

**Blocked schemes**:
- `file://` (local file access)
- `ftp://` (FTP protocol)
- `gopher://` (legacy protocol)
- `data:` (data URIs)
- `javascript:` (JavaScript execution)

### Host Header Validation

Prevents HTTP header injection via malicious hostnames:

**Validation rules**:
- RFC 1123 compliance (alphanumeric, hyphens, dots only)
- No control characters (`\r`, `\n`, `\x00`)
- Length limits: 63 chars per label, 253 chars total
- No path traversal sequences (`../`)

## Input Validation

### Route Names

Route names are validated to prevent DNS-based attacks:

**Rules**:
- Maximum length: 63 characters (RFC 1035 single label limit)
- Allowed characters: `a-z`, `0-9`, `-` (hyphens)
- Must start and end with alphanumeric character
- No consecutive hyphens

**Examples**:
```bash
# Valid
devhost add api 8000
devhost add my-service 8080
devhost add prod-api-v2 8443

# Invalid
devhost add api_service 8000  # underscore not allowed
devhost add -api 8000          # cannot start with hyphen
devhost add api- 8000          # cannot end with hyphen
```

### Port Numbers

Port validation prevents privilege escalation and invalid configurations:

**Rules**:
- Valid range: 1-65535
- Privileged ports (1-1023) require administrator/root access
- Port 0 is rejected (reserved)

### URLs and Hostnames

Full URL validation ensures safe upstream targets:

**Rules**:
- Maximum hostname length: 253 characters (RFC 1035)
- Maximum label length: 63 characters per subdomain
- Valid schemes: `http://` and `https://` only
- IP address validation for literal IPs

## Executable Security

### Path Validation

Devhost validates executable paths before running external tools (Caddy, cloudflared, ngrok):

**Checks**:
- File exists and is executable
- Not in user-writable location (Windows)
- Version verification with timeout (for Caddy)
- Logs warning if executable is in potentially unsafe location

### Subprocess Safety

All subprocess calls are protected against shell injection:

- **No `shell=True`**: All subprocess calls use list-based arguments
- **No `os.system()`**: Avoided entirely (except for Windows ANSI enabler with empty string)
- **Timeout enforcement**: All subprocess calls have timeouts (5s-120s depending on operation)
- **Input sanitization**: User inputs are validated before being passed to subprocesses

## File System Security

### Configuration File Permissions

Configuration files have secure permissions on Unix-like systems:

- **State file** (`~/.devhost/state.yml`): 0600 (owner read/write only)
- **Config file** (`~/.devhost/devhost.json`): 0644 (owner read/write, others read)
- **Private keys**: 0600 (owner read/write only)

Windows uses NTFS ACLs for equivalent protection.

### Certificate Storage

Private keys and certificates are stored securely:

**Storage locations**:
- User Caddy: `~/.local/share/caddy/certificates/`
- System Caddy: `/var/lib/caddy/.local/share/caddy/certificates/`
- Devhost custom: `~/.devhost/certificates/`

**Security measures**:
- Private keys are 0600 (Unix) or owner-only ACL (Windows)
- Certificate expiration warnings (30 days before expiry)
- Automatic validation on startup

### Windows Hosts File Protection

Special protections for Windows hosts file modifications:

**Requirements**:
- Administrator privileges required for all modifications
- Confirmation prompts for destructive operations
- Automatic backups before every change
- Comprehensive audit logging

## TLS/Certificate Verification

### Certificate Verification

TLS certificate verification is enabled by default:

```bash
# Default: verification enabled
curl https://myapp.localhost  # Verifies certificate

# Disable for development (not recommended)
export DEVHOST_VERIFY_CERTS=0
devhost start
```

**Accepted values for DEVHOST_VERIFY_CERTS**:
- Enable: `1`, `true`, `yes`, `on`
- Disable: `0`, `false`, `no`, `off`

⚠️ **Warning**: Disabling certificate verification should only be done in controlled development environments with self-signed certificates.

### Certificate Expiration Monitoring

Devhost monitors certificate expiration and warns you:

- **Default warning period**: 30 days before expiration
- **Check command**: `devhost certificates`
- **Startup validation**: Automatic check when router starts

## Privilege Management

### Principle of Least Privilege

Devhost follows least privilege principles:

**Gateway Mode (Default)**:
- No admin/root required
- Binds to port 7777 (unprivileged)
- No system file modifications

**System Mode**:
- One-time admin setup (Windows)
- Manages Caddy on ports 80/443
- Root/admin required for port binding

**External Mode**:
- No special privileges required
- Generates config snippets only
- User manually applies changes

### Windows Admin Checks

Windows-specific operations require explicit admin checks:

```powershell
# Check if running as admin
net session 2>$null

# If admin required, prompt user to restart elevated
```

Operations requiring admin on Windows:
- Hosts file modifications
- System Mode Caddy management on ports 80/443

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
echo '$env:DEVHOST_ALLOW_PRIVATE_NETWORKS=1' >> $PROFILE
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
