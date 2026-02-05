"""
Minimal metrics collector for the packaged router (`devhost_cli.router.core`).

The in-repo router (`router/app.py`) keeps its own Metrics implementation; this
module exists so the packaged router can stay lightweight and self-contained.
"""

import time


class Metrics:
    def __init__(self) -> None:
        self.start_time = time.time()
        self.requests_total = 0
        self.requests_by_status: dict[int, int] = {}
        self.requests_by_subdomain: dict[str, dict[str, int]] = {}

    def record(self, subdomain: str | None, status_code: int) -> None:
        self.requests_total += 1
        self.requests_by_status[status_code] = self.requests_by_status.get(status_code, 0) + 1
        if not subdomain:
            return
        bucket = self.requests_by_subdomain.setdefault(subdomain, {"count": 0, "errors": 0})
        bucket["count"] += 1
        if status_code >= 400:
            bucket["errors"] += 1

    def snapshot(self) -> dict[str, object]:
        return {
            "uptime_seconds": int(time.time() - self.start_time),
            "requests_total": self.requests_total,
            "requests_by_status": self.requests_by_status,
            "requests_by_subdomain": self.requests_by_subdomain,
        }
