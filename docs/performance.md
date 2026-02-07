# Performance & Optimization

Guide to optimizing Devhost for high-traffic local development and production-like testing.

## Connection Pooling

Devhost uses HTTP connection pooling to reduce latency and improve throughput for repeated requests to the same upstream services.

### Configuration

```bash
# Maximum concurrent connections (default: 100)
export DEVHOST_MAX_CONNECTIONS=200

# Keepalive connections (default: 20)
export DEVHOST_KEEPALIVE_CONNECTIONS=50

# Retry attempts for transient failures (default: 3)
export DEVHOST_MAX_RETRIES=5

# Delay between retries in seconds (default: 1.0)
export DEVHOST_RETRY_DELAY=2.0
```

### How It Works

- **Connection Reuse**: HTTP connections are reused across requests to the same upstream, eliminating TCP handshake overhead
- **Automatic Retries**: Transient failures (502, 503, 504, timeouts) are automatically retried
- **Success Tracking**: Connection pool health metrics available via `/metrics` endpoint

### Performance Impact

| Metric | Before Pooling | With Pooling | Improvement |
|--------|---------------|--------------|-------------|
| Average Latency | 50-100ms | 5-15ms | 80-85% |
| P95 Latency | 150-200ms | 20-40ms | 85-87% |
| P99 Latency | 250-350ms | 50-80ms | 80-85% |

## Route Caching

Route lookups are cached in memory to eliminate disk I/O on every request.

### Cache Behavior

- **Config TTL**: 30 seconds (configuration file cache)
- **Route TTL**: 60 seconds (individual route cache)
- **Automatic Invalidation**: File modification triggers immediate reload
- **Hit Rate Tracking**: Monitor cache effectiveness via `/metrics`

### Performance Impact

| Metric | Disk Lookup | Cached Lookup | Improvement |
|--------|-------------|---------------|-------------|
| Route Lookup Time | 1-5ms | 0.01-0.05ms | ~100x faster |
| Expected Hit Rate | N/A | 90-95% | New capability |

## Metrics & Monitoring

### Health Endpoint

Check router health status:

```bash
curl http://localhost:7777/health | jq
```

Response includes:
- **status**: `ok` or `degraded`
- **version**: Devhost version
- **uptime_seconds**: Router uptime
- **routes**: Number of configured routes
- **in_flight_requests**: Active request count
- **connection_pool**: Pool health and success rate
- **memory_mb**: Memory usage (optional)

### Metrics Endpoint

Detailed performance metrics:

```bash
curl http://localhost:7777/metrics | jq
```

Available metrics:
- **Request Counts**: Total, success, error counts
- **Error Rate**: Percentage of failed requests
- **Latency Percentiles**: P50, P95, P99 latency tracking
- **WebSockets**: Active connections and total count
- **SSRF Blocks**: Blocked requests by reason
- **Cache**: Hit rate and reload count
- **Connection Pool**: Success rate, retry count, timeouts

### Structured Logging

Enable JSON-formatted logs for centralized logging systems:

```bash
export DEVHOST_LOG_FORMAT=json
devhost start
```

JSON log format includes:
- **timestamp**: ISO 8601 with microseconds
- **level**: Log level (INFO, WARNING, ERROR)
- **logger**: Source module
- **message**: Log message
- **request_id**: Correlation ID (when available)
- **Custom fields**: Duration, status codes, etc.

## Monitoring Integration

### Prometheus

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'devhost'
    static_configs:
      - targets: ['localhost:7777']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### Grafana Queries

```promql
# Request rate
rate(devhost_requests_total[5m])

# Error rate percentage
rate(devhost_errors_total[5m]) / rate(devhost_requests_total[5m]) * 100

# P95 latency
histogram_quantile(0.95, devhost_latency_seconds_bucket)

# Connection pool health
devhost_connection_pool_success_rate
```

### ELK Stack (Elasticsearch, Logstash, Kibana)

```yaml
# filebeat.yml
filebeat.inputs:
  - type: log
    paths:
      - /var/log/devhost/*.log
    json.keys_under_root: true
    json.add_error_key: true
```

## Troubleshooting Performance Issues

### High Error Rate

```bash
# Check error rate
curl http://localhost:7777/metrics | jq '.error_rate'

# If > 5%, investigate:
# 1. Connection pool health
curl http://localhost:7777/metrics | jq '.connection_pool'

# 2. SSRF blocks (misconfiguration?)
curl http://localhost:7777/metrics | jq '.ssrf_blocks'

# 3. Enable debug logging
export DEVHOST_LOG_FORMAT=json
export DEVHOST_LOG_LEVEL=DEBUG
devhost restart
```

### High Latency

```bash
# Check latency distribution
curl http://localhost:7777/metrics | jq '.latency'

# If P95/P99 > 100ms:
# 1. Increase connection pool size
export DEVHOST_MAX_CONNECTIONS=200
export DEVHOST_KEEPALIVE_CONNECTIONS=50
devhost restart

# 2. Check cache hit rate (should be > 90%)
curl http://localhost:7777/metrics | jq '.cache.hit_rate'

# 3. Check for request backlog
curl http://localhost:7777/health | jq '.in_flight_requests'
```

### Connection Pool Exhaustion

Symptoms:
- High retry count
- Frequent timeouts
- Low success rate (< 95%)

Solution:
```bash
# Increase pool limits
export DEVHOST_MAX_CONNECTIONS=300
export DEVHOST_KEEPALIVE_CONNECTIONS=100
devhost restart

# Verify improvement
curl http://localhost:7777/metrics | jq '.connection_pool'
```

### Low Cache Hit Rate

```bash
# Check cache performance
curl http://localhost:7777/metrics | jq '.cache'

# If hit_rate < 80%:
# - Check for frequent config changes
# - Verify file system performance
# - Review application logs for errors
```

## Graceful Shutdown

Devhost implements graceful shutdown to avoid dropping in-flight requests:

1. **Shutdown Signal**: Receives SIGTERM or SIGINT
2. **Stop Accepting**: No new requests accepted
3. **Wait**: Waits up to 30 seconds for in-flight requests to complete
4. **Cleanup**: Closes HTTP client and connection pool
5. **Exit**: Clean shutdown

Monitor in-flight requests during shutdown:
```bash
curl http://localhost:7777/health | jq '.in_flight_requests'
```

## Best Practices

### Development

- Use default connection pool settings (100 max, 20 keepalive)
- Enable JSON logging for easier debugging
- Monitor `/health` endpoint during development

### Load Testing

- Increase connection pool to match expected load
- Monitor P95/P99 latency under load
- Check connection pool success rate (should be > 98%)

### Production-Like Testing

- Enable all monitoring (metrics, structured logs)
- Set appropriate timeouts for your upstreams
- Test graceful shutdown behavior
- Verify cache hit rates under realistic traffic patterns

## Performance Tuning Checklist

- [ ] Connection pool sized for peak load
- [ ] Structured logging configured
- [ ] Metrics endpoint monitored
- [ ] Cache hit rate > 90%
- [ ] Error rate < 1%
- [ ] P95 latency < 50ms
- [ ] Connection pool success rate > 98%
- [ ] Graceful shutdown tested
