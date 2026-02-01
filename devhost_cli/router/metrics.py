"""
Request metrics tracking.
"""

import time


class Metrics:
    """Track request counts, status codes, and per-subdomain statistics."""

    def __init__(self) -> None:
        self.requests_total = 0
        self.requests_by_status: dict[int, int] = {}
        self.requests_by_subdomain: dict[str, dict[str, int]] = {}
        self.start_time = time.time()

    def record(self, subdomain: str | None, status_code: int) -> None:
        """Record a request with its subdomain and status code."""
        self.requests_total += 1
        self.requests_by_status[status_code] = self.requests_by_status.get(status_code, 0) + 1
        if subdomain:
            bucket = self.requests_by_subdomain.setdefault(subdomain, {"count": 0, "errors": 0})
            bucket["count"] += 1
            if status_code >= 400:
                bucket["errors"] += 1

    def snapshot(self) -> dict[str, object]:
        """Return current metrics snapshot."""
        return {
            "uptime_seconds": int(time.time() - self.start_time),
            "requests_total": self.requests_total,
            "requests_by_status": self.requests_by_status,
            "requests_by_subdomain": self.requests_by_subdomain,
        }
