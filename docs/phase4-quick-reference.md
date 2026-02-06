# Phase 4 Quick Reference

Quick lookup guide for Phase 4 features, configuration, and troubleshooting.

---

## Environment Variables

```bash
# Connection Pooling (L-14)
export DEVHOST_MAX_CONNECTIONS=100        # Max concurrent connections
export DEVHOST_KEEPALIVE_CONNECTIONS=20   # Keepalive connections
export DEVHOST_MAX_RETRIES=3              # Retry attempts
export DEVHOST_RETRY_DELAY=1.0            # Delay between retries (seconds)

# Structured Logging (L-16)
export DEVHOST_LOG_FORMAT=json            # Enable JSON logs (default: text)
```

---

## Metrics Endpoints

### Health Check
```bash
curl http://localhost:7777/health | jq
```

**Response**:
```json
{
  "status": "ok",
  "version": "3.0.0",
  "uptime_seconds": 3600,
  "routes": 5,
  "in_flight_requests": 2,
  "connection_pool": {
    "healthy": true,
    "success_rate": 98.5
  },
  "memory_mb": 42.3
}
```

### Enhanced Metrics
```bash
curl http://localhost:7777/metrics | jq
```

**Response**:
```json
{
  "total": 1250,
  "success": 1200,
  "error": 50,
  "error_rate": 4.0,
  
  "latency": {
    "samples": 1000,
    "p50": 25.3,
    "p95": 89.7,
    "p99": 142.5
  },
  
  "websockets": {
    "active": 5,
    "total": 47
  },
  
  "ssrf_blocks": {
    "private_network": 12,
    "metadata_endpoint": 3
  },
  
  "cache": {
    "hits": 450,
    "misses": 25,
    "hit_rate": 94.74
  },
  
  "connection_pool": {
    "requests": 1250,
    "successes": 1200,
    "retries": 15,
    "success_rate": 96.0
  }
}
```

---

## Configuration Limits

### Route Names (L-13)
- **Max Length**: 63 characters (RFC 1035 single label limit)
- **Allowed Characters**: `a-z`, `0-9`, `-` (hyphens)
- **Format**: Must start/end with alphanumeric

**Valid Examples**:
```bash
devhost add api 8000           # ✅ Simple name
devhost add my-service 8080    # ✅ With hyphens
devhost add prod-api-v2 8443   # ✅ Max 63 chars
```

**Invalid Examples**:
```bash
devhost add api_service 8000   # ❌ Underscores not allowed
devhost add -api 8000          # ❌ Cannot start with hyphen
devhost add api- 8000          # ❌ Cannot end with hyphen
devhost add very-long-service-name-that-exceeds-the-maximum-allowed-length-of-63-characters 8000  # ❌ Too long
```

### Hostnames (L-13)
- **Max Total Length**: 253 characters (RFC 1035 domain name limit)
- **Max Label Length**: 63 characters per label (e.g., `subdomain.example.com`)

### Port Range
- **Valid Range**: 1-65535
- **Privileged Ports**: 1-1023 (requires admin/root)

### Subprocess Timeouts (L-12)
```python
SUBPROCESS_TIMEOUTS = {
    "quick": 5,          # version checks, format
    "standard": 30,      # caddy start/stop/reload
    "long": 60,          # proxy transfer, attach
    "caddy_validate": 10,
    "tunnel": 120        # ngrok/cloudflare operations
}
```

---

## Validation Rules

### Config Validation (L-20)
Run on startup or manually:
```bash
devhost validate
```

**Checks**:
- ✅ Route name format (1-63 chars, alphanumeric + hyphens)
- ✅ Target format (port, `host:port`, `http(s)://...`)
- ✅ Port range (1-65535)
- ✅ URL scheme (http/https only)
- ✅ File permissions (owner-only on Unix)

### Executable Validation (L-11)
Validates Caddy binary before execution:
```bash
devhost proxy validate
```

**Checks**:
- ✅ File exists and is executable
- ✅ Not user-writable (security risk)
- ✅ Caddy version check (timeout: 10s)
- ✅ Path safety (Windows USERPROFILE, Unix owner-write)

---

## Performance Benchmarks

### Connection Pooling (L-14)
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Latency (avg)** | 50-100ms | 5-15ms | **80-85%** |
| **Latency (P95)** | 150-200ms | 20-40ms | **85-87%** |
| **Latency (P99)** | 250-350ms | 50-80ms | **80-85%** |
| **Memory** | Baseline | +5-10MB | Negligible |

### Route Caching (L-15)
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Route Lookup** | 1-5ms (disk I/O) | 0.01-0.05ms (memory) | **~100x faster** |
| **Cache Hit Rate** | N/A | 90-95% | New metric |

---

## Troubleshooting

### High Error Rate
```bash
# Check metrics
curl http://localhost:7777/metrics | jq '.error_rate'

# If > 5%, check:
# 1. Connection pool health
curl http://localhost:7777/metrics | jq '.connection_pool'

# 2. SSRF blocks (may indicate misconfiguration)
curl http://localhost:7777/metrics | jq '.ssrf_blocks'

# 3. Logs (enable JSON for structured analysis)
export DEVHOST_LOG_FORMAT=json
devhost start
```

### Slow Requests (High Latency)
```bash
# Check latency percentiles
curl http://localhost:7777/metrics | jq '.latency'

# If P95/P99 > 100ms, check:
# 1. Connection pool config (increase max connections)
export DEVHOST_MAX_CONNECTIONS=200
export DEVHOST_KEEPALIVE_CONNECTIONS=50

# 2. Cache hit rate (should be > 90%)
curl http://localhost:7777/metrics | jq '.cache.hit_rate'

# 3. In-flight requests (if high, scale horizontally)
curl http://localhost:7777/health | jq '.in_flight_requests'
```

### Health Check Failures
```bash
# Check health status
curl http://localhost:7777/health | jq

# If unhealthy, check:
# 1. Connection pool success rate
curl http://localhost:7777/health | jq '.connection_pool.success_rate'
# If < 95%, check upstream services

# 2. In-flight requests (if high, may indicate stuck requests)
curl http://localhost:7777/health | jq '.in_flight_requests'

# 3. Memory usage (if high, may indicate leak)
curl http://localhost:7777/health | jq '.memory_mb'
```

### Connection Pool Exhaustion
```bash
# Symptoms:
# - High retry count
# - Timeouts
# - Low success rate

# Check metrics
curl http://localhost:7777/metrics | jq '.connection_pool'

# Solution: Increase pool size
export DEVHOST_MAX_CONNECTIONS=200
export DEVHOST_KEEPALIVE_CONNECTIONS=50
devhost restart
```

### Cache Misses
```bash
# Check cache hit rate
curl http://localhost:7777/metrics | jq '.cache.hit_rate'

# If < 80%, check:
# 1. TTL settings (may be too short)
# 2. Config file modification frequency
# 3. File I/O errors (check logs)

# Solution: Increase TTL (requires code change)
# Default: CONFIG_TTL=30s, ROUTE_TTL=60s
```

---

## Monitoring Integration

### Prometheus
```yaml
# Add to prometheus.yml
scrape_configs:
  - job_name: 'devhost'
    static_configs:
      - targets: ['localhost:7777']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### Grafana Dashboard Queries
```promql
# Request rate
rate(devhost_requests_total[5m])

# Error rate
rate(devhost_errors_total[5m]) / rate(devhost_requests_total[5m])

# Latency P95
histogram_quantile(0.95, devhost_latency_seconds_bucket)

# Connection pool success rate
devhost_connection_pool_success_rate
```

### ELK Stack (JSON Logs)
```bash
# Enable JSON logging
export DEVHOST_LOG_FORMAT=json
devhost start

# Filebeat configuration
filebeat.inputs:
  - type: log
    paths:
      - /var/log/devhost/*.log
    json.keys_under_root: true
    json.add_error_key: true
```

---

## Maintenance Commands

### Check System Status
```bash
# Quick health check
devhost status

# Detailed health check
curl http://localhost:7777/health | jq

# View metrics
curl http://localhost:7777/metrics | jq
```

### Validate Configuration
```bash
# Validate config file
devhost validate

# Check for issues
devhost diagnose
```

### Performance Analysis
```bash
# Check latency distribution
curl http://localhost:7777/metrics | jq '.latency'

# Monitor real-time
watch -n 1 'curl -s http://localhost:7777/metrics | jq ".latency"'
```

### Restart Router
```bash
# Graceful restart (waits for in-flight requests)
devhost restart

# Force restart (immediate)
devhost stop && devhost start
```

---

## Feature Flags

### Opt-In Features
```bash
# JSON logging (disabled by default)
export DEVHOST_LOG_FORMAT=json

# Security headers (disabled by default)
export DEVHOST_ENABLE_SECURITY_HEADERS=1

# Private network access (disabled by default)
export DEVHOST_ALLOW_PRIVATE_NETWORKS=1
```

### Opt-Out Features
```bash
# Connection pooling (enabled by default)
export DEVHOST_MAX_CONNECTIONS=0  # Disable pooling

# Route caching (enabled by default)
# No env var yet, requires code change to disable
```

---

## Common Issues

### Issue: "Route name too long"
**Cause**: Route name exceeds 63 characters (RFC 1035 limit)  
**Solution**: Use shorter names or abbreviations
```bash
# ❌ Too long
devhost add production-api-service-backend-v2 8000

# ✅ Better
devhost add prod-api 8000
```

### Issue: "Invalid target format"
**Cause**: Target doesn't match expected format  
**Solution**: Use valid format
```bash
# Valid formats
devhost add api 8000                    # Port only
devhost add api 127.0.0.1:8000         # Host:port
devhost add api http://localhost:8000  # Full URL
devhost add api https://api.example.com:8443  # HTTPS URL
```

### Issue: "Executable path not secure"
**Cause**: Caddy binary is user-writable (security risk)  
**Solution**: Use system-installed Caddy or secure the binary
```bash
# Unix: Remove user-write permission
chmod 755 /usr/local/bin/caddy

# Windows: Use system PATH or secure location
# Avoid: C:\Users\<username>\Downloads\caddy.exe
```

### Issue: "Subprocess timeout"
**Cause**: Operation exceeded timeout limit  
**Solution**: Check network connectivity or increase timeout (requires code change)
```bash
# Typical timeouts:
# - Quick: 5s (version checks)
# - Standard: 30s (start/stop)
# - Long: 60s (proxy operations)
# - Tunnel: 120s (network operations)
```

---

## Related Documentation

- [Phase 4 Completion Summary](phase4-completion-summary.md) - Full implementation details
- [Security Configuration](security-configuration.md) - Security features and best practices
- [Architecture](architecture.md) - System design and components
- [CLI Reference](cli.md) - Command-line interface guide

---

## Support

For issues or questions:
- **GitHub Issues**: https://github.com/yourusername/devhost/issues
- **Documentation**: https://devhost.readthedocs.io
- **Discord**: https://discord.gg/devhost
