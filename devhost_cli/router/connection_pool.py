"""
HTTP connection pooling optimization for proxy requests (Phase 4 L-14).

Provides optimized httpx client configuration with:
- Connection pooling (max connections, keep-alive)
- Timeout configuration (connect, read, write, pool)
- Retry logic for transient failures
- Connection metrics and monitoring
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("devhost.router.pool")

# Connection pool configuration from environment or defaults
MAX_CONNECTIONS = int(os.getenv("DEVHOST_MAX_CONNECTIONS", "100"))
MAX_KEEPALIVE_CONNECTIONS = int(os.getenv("DEVHOST_MAX_KEEPALIVE", "20"))
KEEPALIVE_EXPIRY = float(os.getenv("DEVHOST_KEEPALIVE_EXPIRY", "5.0"))  # seconds

# Timeout configuration (in seconds)
CONNECT_TIMEOUT = float(os.getenv("DEVHOST_CONNECT_TIMEOUT", "5.0"))
READ_TIMEOUT = float(os.getenv("DEVHOST_READ_TIMEOUT", "30.0"))
WRITE_TIMEOUT = float(os.getenv("DEVHOST_WRITE_TIMEOUT", "30.0"))
POOL_TIMEOUT = float(os.getenv("DEVHOST_POOL_TIMEOUT", "5.0"))

# Retry configuration
MAX_RETRIES = int(os.getenv("DEVHOST_MAX_RETRIES", "3"))
RETRY_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}  # Safe to retry


class ConnectionPoolMetrics:
    """Track connection pool metrics."""
    
    def __init__(self):
        self.requests_sent = 0
        self.requests_failed = 0
        self.retries_attempted = 0
        self.connections_created = 0
        self.timeouts = 0
    
    def record_request(self):
        """Record a successful request."""
        self.requests_sent += 1
    
    def record_failure(self):
        """Record a failed request."""
        self.requests_failed += 1
    
    def record_retry(self):
        """Record a retry attempt."""
        self.retries_attempted += 1
    
    def record_timeout(self):
        """Record a timeout."""
        self.timeouts += 1
    
    def snapshot(self) -> dict:
        """Get current metrics snapshot."""
        return {
            "requests_sent": self.requests_sent,
            "requests_failed": self.requests_failed,
            "retries_attempted": self.retries_attempted,
            "timeouts": self.timeouts,
            "success_rate": (
                self.requests_sent / (self.requests_sent + self.requests_failed)
                if (self.requests_sent + self.requests_failed) > 0
                else 1.0
            ),
        }


# Global metrics instance
_metrics = ConnectionPoolMetrics()


def get_pool_metrics() -> dict:
    """Get connection pool metrics snapshot."""
    return _metrics.snapshot()


def create_http_client(
    max_connections: Optional[int] = None,
    max_keepalive: Optional[int] = None,
    keepalive_expiry: Optional[float] = None,
    connect_timeout: Optional[float] = None,
    read_timeout: Optional[float] = None,
    write_timeout: Optional[float] = None,
    pool_timeout: Optional[float] = None,
) -> httpx.AsyncClient:
    """
    Create an optimized httpx AsyncClient with connection pooling.
    
    Args:
        max_connections: Maximum number of concurrent connections
        max_keepalive: Maximum number of keep-alive connections in pool
        keepalive_expiry: Time in seconds to keep idle connections alive
        connect_timeout: Connection timeout in seconds
        read_timeout: Read timeout in seconds
        write_timeout: Write timeout in seconds
        pool_timeout: Pool acquisition timeout in seconds
    
    Returns:
        Configured httpx.AsyncClient
    
    Example:
        >>> client = create_http_client()
        >>> async with client:
        ...     response = await client.get("http://example.com")
    """
    # Use provided values or fall back to environment/defaults
    limits = httpx.Limits(
        max_connections=max_connections or MAX_CONNECTIONS,
        max_keepalive_connections=max_keepalive or MAX_KEEPALIVE_CONNECTIONS,
        keepalive_expiry=keepalive_expiry or KEEPALIVE_EXPIRY,
    )
    
    timeout = httpx.Timeout(
        connect=connect_timeout or CONNECT_TIMEOUT,
        read=read_timeout or READ_TIMEOUT,
        write=write_timeout or WRITE_TIMEOUT,
        pool=pool_timeout or POOL_TIMEOUT,
    )
    
    logger.debug(
        "Creating HTTP client: max_conn=%d, keepalive=%d, keepalive_expiry=%.1fs",
        limits.max_connections,
        limits.max_keepalive_connections,
        limits.keepalive_expiry,
    )
    
    # Create client with optimized settings
    client = httpx.AsyncClient(
        limits=limits,
        timeout=timeout,
        follow_redirects=True,  # Follow redirects automatically
        http2=False,  # Disable HTTP/2 for now (compatibility)
    )
    
    return client


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs
) -> httpx.Response:
    """
    Execute HTTP request with automatic retry logic.
    
    Retries on:
    - Connection errors
    - Timeout errors
    - 502/503/504 status codes (transient server errors)
    
    Only retries safe methods (GET, HEAD, OPTIONS, TRACE).
    
    Args:
        client: httpx.AsyncClient to use
        method: HTTP method (GET, POST, etc.)
        url: URL to request
        **kwargs: Additional arguments to pass to client.request()
    
    Returns:
        httpx.Response from successful request
    
    Raises:
        httpx.RequestError: If all retries fail
    """
    last_error = None
    retries = MAX_RETRIES if method.upper() in RETRY_METHODS else 1
    
    for attempt in range(retries):
        try:
            response = await client.request(method, url, **kwargs)
            
            # Check if response is retriable (502/503/504)
            if response.status_code in {502, 503, 504} and attempt < retries - 1:
                _metrics.record_retry()
                logger.debug(
                    "Retrying %s %s (status %d, attempt %d/%d)",
                    method,
                    url,
                    response.status_code,
                    attempt + 1,
                    retries,
                )
                continue
            
            _metrics.record_request()
            return response
            
        except httpx.TimeoutException as e:
            _metrics.record_timeout()
            last_error = e
            if attempt < retries - 1:
                _metrics.record_retry()
                logger.debug("Timeout on %s %s (attempt %d/%d)", method, url, attempt + 1, retries)
                continue
            
        except httpx.RequestError as e:
            last_error = e
            if attempt < retries - 1:
                _metrics.record_retry()
                logger.debug("Request error on %s %s: %s (attempt %d/%d)", method, url, e, attempt + 1, retries)
                continue
    
    # All retries failed
    _metrics.record_failure()
    if last_error:
        raise last_error
    else:
        raise httpx.RequestError(f"Request failed after {retries} attempts")
