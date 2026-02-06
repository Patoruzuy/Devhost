"""
Enhanced metrics collector for the packaged router (Phase 4 L-17).

Provides detailed metrics including:
- Request counts and error rates
- Latency percentiles (p50, p95, p99)
- Per-route statistics
- WebSocket connection tracking
- SSRF block counts
"""

import time
from collections import deque
from typing import Dict, List, Optional


def calculate_percentile(values: List[float], percentile: float) -> float:
    """
    Calculate percentile from a list of values.
    
    Args:
        values: List of numeric values
        percentile: Percentile to calculate (0-100)
        
    Returns:
        Percentile value or 0.0 if no values
    """
    if not values:
        return 0.0
    
    sorted_values = sorted(values)
    index = int((percentile / 100.0) * len(sorted_values))
    if index >= len(sorted_values):
        index = len(sorted_values) - 1
    return sorted_values[index]


class Metrics:
    """Enhanced metrics collector with latency tracking and detailed statistics."""
    
    def __init__(self, max_latency_samples: int = 1000) -> None:
        self.start_time = time.time()
        self.requests_total = 0
        self.requests_by_status: dict[int, int] = {}
        self.requests_by_subdomain: dict[str, dict[str, int]] = {}
        
        # Latency tracking (Phase 4 L-17)
        self.max_latency_samples = max_latency_samples
        self.latency_samples: deque = deque(maxlen=max_latency_samples)
        
        # WebSocket tracking
        self.websocket_connections_active = 0
        self.websocket_connections_total = 0
        
        # SSRF blocks
        self.ssrf_blocks_total = 0
        self.ssrf_blocks_by_reason: dict[str, int] = {}

    def record(self, subdomain: str | None, status_code: int, latency_ms: Optional[float] = None) -> None:
        """
        Record a request with optional latency.
        
        Args:
            subdomain: Subdomain for the request
            status_code: HTTP status code
            latency_ms: Request latency in milliseconds
        """
        self.requests_total += 1
        self.requests_by_status[status_code] = self.requests_by_status.get(status_code, 0) + 1
        
        # Record latency if provided (Phase 4 L-17)
        if latency_ms is not None:
            self.latency_samples.append(latency_ms)
        
        if not subdomain:
            return
        bucket = self.requests_by_subdomain.setdefault(subdomain, {"count": 0, "errors": 0})
        bucket["count"] += 1
        if status_code >= 400:
            bucket["errors"] += 1
    
    def record_websocket_connected(self) -> None:
        """Record a new WebSocket connection."""
        self.websocket_connections_active += 1
        self.websocket_connections_total += 1
    
    def record_websocket_disconnected(self) -> None:
        """Record a WebSocket disconnection."""
        if self.websocket_connections_active > 0:
            self.websocket_connections_active -= 1
    
    def record_ssrf_block(self, reason: str = "unknown") -> None:
        """
        Record an SSRF block.
        
        Args:
            reason: Reason for the block (e.g., "private_ip", "localhost", "blacklisted")
        """
        self.ssrf_blocks_total += 1
        self.ssrf_blocks_by_reason[reason] = self.ssrf_blocks_by_reason.get(reason, 0) + 1
    
    def get_latency_percentiles(self) -> Dict[str, float]:
        """
        Calculate latency percentiles from recent samples.
        
        Returns:
            Dict with p50, p95, and p99 latency in milliseconds
        """
        if not self.latency_samples:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        
        samples = list(self.latency_samples)
        return {
            "p50": round(calculate_percentile(samples, 50), 2),
            "p95": round(calculate_percentile(samples, 95), 2),
            "p99": round(calculate_percentile(samples, 99), 2),
        }
    
    def get_error_rate(self) -> float:
        """
        Calculate overall error rate.
        
        Returns:
            Error rate as a percentage (0-100)
        """
        if self.requests_total == 0:
            return 0.0
        
        error_count = sum(
            count for status, count in self.requests_by_status.items()
            if status >= 400
        )
        return round((error_count / self.requests_total) * 100, 2)

    def snapshot(self) -> dict[str, object]:
        """
        Get a snapshot of all metrics.
        
        Returns:
            Dict with all current metrics including enhanced L-17 metrics
        """
        return {
            "uptime_seconds": int(time.time() - self.start_time),
            "requests_total": self.requests_total,
            "requests_by_status": self.requests_by_status,
            "requests_by_subdomain": self.requests_by_subdomain,
            # Enhanced metrics (Phase 4 L-17)
            "latency": self.get_latency_percentiles(),
            "error_rate": self.get_error_rate(),
            "websocket": {
                "connections_active": self.websocket_connections_active,
                "connections_total": self.websocket_connections_total,
            },
            "ssrf": {
                "blocks_total": self.ssrf_blocks_total,
                "blocks_by_reason": self.ssrf_blocks_by_reason,
            },
        }

