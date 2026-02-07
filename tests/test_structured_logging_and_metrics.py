"""
Tests for structured logging (Phase 4 L-16) and enhanced metrics (Phase 4 L-17).
"""

import json
import logging
import os
import unittest
from io import StringIO
from unittest.mock import patch

from devhost_cli.router.metrics import Metrics, calculate_percentile
from devhost_cli.structured_logging import (
    JSONFormatter,
    RequestLogger,
    configure_structured_logging,
    is_json_logging_enabled,
)


class TestJSONFormatter(unittest.TestCase):
    """Test JSON log formatter (Phase 4 L-16)."""

    def setUp(self):
        """Create formatter instance."""
        self.formatter = JSONFormatter()

    def test_basic_log_formatting(self):
        """Test basic log record formatting."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = self.formatter.format(record)
        data = json.loads(result)

        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["logger"], "test.logger")
        self.assertEqual(data["message"], "Test message")
        self.assertIn("timestamp", data)
        self.assertIn("file", data)

    def test_log_with_request_id(self):
        """Test log record with request ID."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Request handled",
            args=(),
            exc_info=None,
        )
        record.request_id = "abc123"

        result = self.formatter.format(record)
        data = json.loads(result)

        self.assertEqual(data["request_id"], "abc123")

    def test_log_with_exception(self):
        """Test log record with exception info."""
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        result = self.formatter.format(record)
        data = json.loads(result)

        self.assertIn("exception", data)
        self.assertIn("ValueError", data["exception"])

    def test_log_with_extra_fields(self):
        """Test log record with extra fields."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Custom data",
            args=(),
            exc_info=None,
        )
        record.user_id = 123
        record.session_id = "xyz789"

        result = self.formatter.format(record)
        data = json.loads(result)

        self.assertEqual(data["user_id"], 123)
        self.assertEqual(data["session_id"], "xyz789")


class TestStructuredLogging(unittest.TestCase):
    """Test structured logging configuration."""

    def test_is_json_logging_enabled_default(self):
        """Test JSON logging detection with default."""
        # Clear environment
        if "DEVHOST_LOG_FORMAT" in os.environ:
            del os.environ["DEVHOST_LOG_FORMAT"]

        self.assertFalse(is_json_logging_enabled())

    def test_is_json_logging_enabled_json(self):
        """Test JSON logging detection when enabled."""
        os.environ["DEVHOST_LOG_FORMAT"] = "json"
        try:
            self.assertTrue(is_json_logging_enabled())
        finally:
            del os.environ["DEVHOST_LOG_FORMAT"]

    def test_is_json_logging_enabled_text(self):
        """Test JSON logging detection when disabled."""
        os.environ["DEVHOST_LOG_FORMAT"] = "text"
        try:
            self.assertFalse(is_json_logging_enabled())
        finally:
            del os.environ["DEVHOST_LOG_FORMAT"]

    def test_configure_structured_logging(self):
        """Test structured logging configuration."""
        # Capture logging to verify it's configured
        with patch("logging.basicConfig") as mock_config:
            configure_structured_logging(level="DEBUG")

            mock_config.assert_called_once()
            args, kwargs = mock_config.call_args
            self.assertEqual(kwargs["level"], "DEBUG")
            self.assertTrue(kwargs["force"])


class TestRequestLogger(unittest.TestCase):
    """Test request logger helper."""

    def setUp(self):
        """Create logger and stream for capturing output."""
        self.stream = StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(JSONFormatter())

        self.base_logger = logging.getLogger("test.request")
        self.base_logger.handlers = [self.handler]
        self.base_logger.setLevel(logging.DEBUG)

        self.request_logger = RequestLogger(self.base_logger, request_id="req-123")

    def test_info_with_request_id(self):
        """Test info logging includes request ID."""
        self.request_logger.info("Test message")

        output = self.stream.getvalue()
        data = json.loads(output)

        self.assertEqual(data["message"], "Test message")
        self.assertEqual(data["request_id"], "req-123")
        self.assertEqual(data["level"], "INFO")

    def test_error_with_request_id(self):
        """Test error logging includes request ID."""
        self.request_logger.error("Error occurred")

        output = self.stream.getvalue()
        data = json.loads(output)

        self.assertEqual(data["message"], "Error occurred")
        self.assertEqual(data["request_id"], "req-123")
        self.assertEqual(data["level"], "ERROR")


class TestPercentileCalculation(unittest.TestCase):
    """Test percentile calculation helper (Phase 4 L-17)."""

    def test_percentile_empty_list(self):
        """Test percentile with empty list."""
        self.assertEqual(calculate_percentile([], 50), 0.0)

    def test_percentile_p50(self):
        """Test median (p50) calculation."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_percentile(values, 50)
        self.assertAlmostEqual(result, 3.0, places=1)

    def test_percentile_p95(self):
        """Test p95 calculation."""
        values = list(range(1, 101))  # 1-100
        result = calculate_percentile(values, 95)
        self.assertGreaterEqual(result, 95)

    def test_percentile_p99(self):
        """Test p99 calculation."""
        values = list(range(1, 101))  # 1-100
        result = calculate_percentile(values, 99)
        self.assertGreaterEqual(result, 99)


class TestEnhancedMetrics(unittest.TestCase):
    """Test enhanced metrics tracking (Phase 4 L-17)."""

    def setUp(self):
        """Create metrics instance."""
        self.metrics = Metrics(max_latency_samples=10)

    def test_record_with_latency(self):
        """Test recording request with latency."""
        self.metrics.record("api", 200, latency_ms=50.5)

        self.assertEqual(self.metrics.requests_total, 1)
        self.assertEqual(len(self.metrics.latency_samples), 1)
        self.assertIn(50.5, self.metrics.latency_samples)

    def test_latency_percentiles(self):
        """Test latency percentile calculation."""
        # Add some latency samples
        for ms in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            self.metrics.record("api", 200, latency_ms=float(ms))

        percentiles = self.metrics.get_latency_percentiles()

        self.assertIn("p50", percentiles)
        self.assertIn("p95", percentiles)
        self.assertIn("p99", percentiles)
        self.assertGreater(percentiles["p50"], 0)
        self.assertGreater(percentiles["p95"], percentiles["p50"])

    def test_latency_samples_limit(self):
        """Test that latency samples are limited."""
        # Add more samples than the limit
        for i in range(20):
            self.metrics.record("api", 200, latency_ms=float(i))

        # Should only keep last 10
        self.assertEqual(len(self.metrics.latency_samples), 10)

    def test_websocket_tracking(self):
        """Test WebSocket connection tracking."""
        self.assertEqual(self.metrics.websocket_connections_active, 0)
        self.assertEqual(self.metrics.websocket_connections_total, 0)

        # Connect
        self.metrics.record_websocket_connected()
        self.assertEqual(self.metrics.websocket_connections_active, 1)
        self.assertEqual(self.metrics.websocket_connections_total, 1)

        # Connect another
        self.metrics.record_websocket_connected()
        self.assertEqual(self.metrics.websocket_connections_active, 2)
        self.assertEqual(self.metrics.websocket_connections_total, 2)

        # Disconnect one
        self.metrics.record_websocket_disconnected()
        self.assertEqual(self.metrics.websocket_connections_active, 1)
        self.assertEqual(self.metrics.websocket_connections_total, 2)

    def test_ssrf_block_tracking(self):
        """Test SSRF block tracking."""
        self.assertEqual(self.metrics.ssrf_blocks_total, 0)

        self.metrics.record_ssrf_block(reason="private_ip")
        self.assertEqual(self.metrics.ssrf_blocks_total, 1)
        self.assertEqual(self.metrics.ssrf_blocks_by_reason["private_ip"], 1)

        self.metrics.record_ssrf_block(reason="private_ip")
        self.metrics.record_ssrf_block(reason="localhost")

        self.assertEqual(self.metrics.ssrf_blocks_total, 3)
        self.assertEqual(self.metrics.ssrf_blocks_by_reason["private_ip"], 2)
        self.assertEqual(self.metrics.ssrf_blocks_by_reason["localhost"], 1)

    def test_error_rate_calculation(self):
        """Test error rate calculation."""
        # No requests
        self.assertEqual(self.metrics.get_error_rate(), 0.0)

        # Add successful requests
        self.metrics.record("api", 200)
        self.metrics.record("api", 200)
        self.metrics.record("api", 200)

        # Add errors
        self.metrics.record("api", 500)

        # 1 error out of 4 = 25%
        self.assertEqual(self.metrics.get_error_rate(), 25.0)

    def test_snapshot_includes_enhanced_metrics(self):
        """Test that snapshot includes all enhanced metrics."""
        self.metrics.record("api", 200, latency_ms=50.0)
        self.metrics.record_websocket_connected()
        self.metrics.record_ssrf_block(reason="test")

        snapshot = self.metrics.snapshot()

        # Basic metrics
        self.assertIn("uptime_seconds", snapshot)
        self.assertIn("requests_total", snapshot)

        # Enhanced metrics (Phase 4 L-17)
        self.assertIn("latency", snapshot)
        self.assertIn("error_rate", snapshot)
        self.assertIn("websocket", snapshot)
        self.assertIn("ssrf", snapshot)

        # Check structure
        self.assertIn("p50", snapshot["latency"])
        self.assertIn("p95", snapshot["latency"])
        self.assertIn("p99", snapshot["latency"])

        self.assertIn("connections_active", snapshot["websocket"])
        self.assertIn("connections_total", snapshot["websocket"])

        self.assertIn("blocks_total", snapshot["ssrf"])
        self.assertIn("blocks_by_reason", snapshot["ssrf"])


if __name__ == "__main__":
    unittest.main()
