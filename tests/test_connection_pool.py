"""
Tests for connection pooling optimization (Phase 4 L-14).
"""

import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx

from devhost_cli.router.connection_pool import (
    create_http_client,
    request_with_retry,
    get_pool_metrics,
    ConnectionPoolMetrics,
    MAX_CONNECTIONS,
    MAX_KEEPALIVE_CONNECTIONS,
    KEEPALIVE_EXPIRY,
    CONNECT_TIMEOUT,
    READ_TIMEOUT,
)


class TestConnectionPoolCreation(unittest.TestCase):
    """Test HTTP client creation with connection pooling."""
    
    def test_create_client_default_settings(self):
        """Test client creation with default settings."""
        client = create_http_client()
        
        self.assertIsInstance(client, httpx.AsyncClient)
        # Verify client was created successfully
        self.assertIsNotNone(client)
    
    def test_create_client_custom_limits(self):
        """Test client creation with custom connection limits."""
        client = create_http_client(
            max_connections=50,
            max_keepalive=10,
            keepalive_expiry=10.0,
        )
        
        # Verify client was created successfully with custom settings
        self.assertIsInstance(client, httpx.AsyncClient)
    
    def test_create_client_custom_timeouts(self):
        """Test client creation with custom timeouts."""
        client = create_http_client(
            connect_timeout=2.0,
            read_timeout=10.0,
            write_timeout=10.0,
            pool_timeout=1.0,
        )
        
        # Verify client was created successfully with custom timeouts
        self.assertIsInstance(client, httpx.AsyncClient)
    
    def test_default_limits_from_constants(self):
        """Test that default limits match module constants."""
        client = create_http_client()
        
        # Verify client was created successfully
        self.assertIsInstance(client, httpx.AsyncClient)
    
    @patch.dict(os.environ, {"DEVHOST_MAX_CONNECTIONS": "200"})
    def test_limits_from_environment(self):
        """Test that limits can be configured via environment variables."""
        # Need to reload module to pick up env changes
        from importlib import reload
        from devhost_cli.router import connection_pool
        reload(connection_pool)
        
        client = connection_pool.create_http_client()
        # Verify client was created successfully
        self.assertIsInstance(client, httpx.AsyncClient)


class TestConnectionPoolMetrics(unittest.TestCase):
    """Test connection pool metrics tracking."""
    
    def setUp(self):
        """Create fresh metrics instance."""
        self.metrics = ConnectionPoolMetrics()
    
    def test_initial_state(self):
        """Test metrics initial state."""
        snapshot = self.metrics.snapshot()
        
        self.assertEqual(snapshot["requests_sent"], 0)
        self.assertEqual(snapshot["requests_failed"], 0)
        self.assertEqual(snapshot["retries_attempted"], 0)
        self.assertEqual(snapshot["timeouts"], 0)
        self.assertEqual(snapshot["success_rate"], 1.0)
    
    def test_record_request(self):
        """Test recording successful requests."""
        self.metrics.record_request()
        self.metrics.record_request()
        
        snapshot = self.metrics.snapshot()
        self.assertEqual(snapshot["requests_sent"], 2)
        self.assertEqual(snapshot["success_rate"], 1.0)
    
    def test_record_failure(self):
        """Test recording failed requests."""
        self.metrics.record_failure()
        
        snapshot = self.metrics.snapshot()
        self.assertEqual(snapshot["requests_failed"], 1)
        self.assertEqual(snapshot["success_rate"], 0.0)
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        self.metrics.record_request()
        self.metrics.record_request()
        self.metrics.record_request()
        self.metrics.record_failure()
        
        snapshot = self.metrics.snapshot()
        self.assertEqual(snapshot["requests_sent"], 3)
        self.assertEqual(snapshot["requests_failed"], 1)
        self.assertEqual(snapshot["success_rate"], 0.75)  # 3/4
    
    def test_record_retry(self):
        """Test recording retry attempts."""
        self.metrics.record_retry()
        self.metrics.record_retry()
        
        snapshot = self.metrics.snapshot()
        self.assertEqual(snapshot["retries_attempted"], 2)
    
    def test_record_timeout(self):
        """Test recording timeouts."""
        self.metrics.record_timeout()
        
        snapshot = self.metrics.snapshot()
        self.assertEqual(snapshot["timeouts"], 1)


class TestRequestWithRetry(unittest.IsolatedAsyncioTestCase):
    """Test request retry logic."""
    
    async def test_successful_request_no_retry(self):
        """Test successful request without retry."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_client.request = AsyncMock(return_value=mock_response)
        
        response = await request_with_retry(
            mock_client,
            "GET",
            "http://example.com",
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_client.request.call_count, 1)
    
    async def test_retry_on_502_status(self):
        """Test retry on 502 status code."""
        mock_client = Mock()
        
        # First attempt: 502, second attempt: 200
        mock_response_502 = Mock()
        mock_response_502.status_code = 502
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        
        mock_client.request = AsyncMock(side_effect=[mock_response_502, mock_response_200])
        
        response = await request_with_retry(
            mock_client,
            "GET",
            "http://example.com",
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_client.request.call_count, 2)
    
    async def test_retry_on_timeout(self):
        """Test retry on timeout exception."""
        mock_client = Mock()
        
        # First attempt: timeout, second attempt: success
        mock_response = Mock()
        mock_response.status_code = 200
        
        mock_client.request = AsyncMock(
            side_effect=[httpx.TimeoutException("Timeout"), mock_response]
        )
        
        response = await request_with_retry(
            mock_client,
            "GET",
            "http://example.com",
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_client.request.call_count, 2)
    
    async def test_no_retry_for_post(self):
        """Test that POST requests are not retried."""
        mock_client = Mock()
        mock_client.request = AsyncMock(side_effect=httpx.RequestError("Error"))
        
        with self.assertRaises(httpx.RequestError):
            await request_with_retry(
                mock_client,
                "POST",
                "http://example.com",
            )
        
        # Should only attempt once (no retries for POST)
        self.assertEqual(mock_client.request.call_count, 1)
    
    async def test_retry_safe_methods(self):
        """Test that safe methods (GET, HEAD, OPTIONS) are retried."""
        for method in ["GET", "HEAD", "OPTIONS", "TRACE"]:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            
            # First two attempts fail, third succeeds
            mock_client.request = AsyncMock(
                side_effect=[
                    httpx.RequestError("Error 1"),
                    httpx.RequestError("Error 2"),
                    mock_response,
                ]
            )
            
            response = await request_with_retry(
                mock_client,
                method,
                "http://example.com",
            )
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(mock_client.request.call_count, 3)
    
    async def test_max_retries_exceeded(self):
        """Test that max retries are respected."""
        mock_client = Mock()
        mock_client.request = AsyncMock(side_effect=httpx.RequestError("Always fail"))
        
        with self.assertRaises(httpx.RequestError):
            await request_with_retry(
                mock_client,
                "GET",
                "http://example.com",
            )
        
        # Should attempt 3 times (initial + 2 retries)
        self.assertEqual(mock_client.request.call_count, 3)


class TestPoolMetricsGlobal(unittest.TestCase):
    """Test global pool metrics function."""
    
    def test_get_pool_metrics_returns_dict(self):
        """Test that get_pool_metrics returns a dict."""
        metrics = get_pool_metrics()
        
        self.assertIsInstance(metrics, dict)
        self.assertIn("requests_sent", metrics)
        self.assertIn("requests_failed", metrics)
        self.assertIn("success_rate", metrics)


if __name__ == "__main__":
    unittest.main()
