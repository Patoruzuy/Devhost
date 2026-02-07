"""Tests for proxy header sanitization."""

import unittest

import httpx

from devhost_cli.router.core import _sanitize_request_headers, _sanitize_response_headers


class TestProxyHeaderSanitization(unittest.TestCase):
    def test_request_sanitization_removes_hop_by_hop_and_forwarded(self):
        headers = {
            "Connection": "keep-alive, X-Remove",
            "Keep-Alive": "timeout=5",
            "X-Remove": "value",
            "Forwarded": "for=1.2.3.4",
            "X-Forwarded-For": "1.2.3.4",
            "X-Real-IP": "1.2.3.4",
            "Content-Length": "10",
            "X-Custom": "ok",
        }

        sanitized = _sanitize_request_headers(headers)

        self.assertNotIn("Connection", sanitized)
        self.assertNotIn("Keep-Alive", sanitized)
        self.assertNotIn("X-Remove", sanitized)
        self.assertNotIn("Forwarded", sanitized)
        self.assertNotIn("X-Forwarded-For", sanitized)
        self.assertNotIn("X-Real-IP", sanitized)
        self.assertTrue(all(k.lower() != "content-length" for k in sanitized))
        self.assertEqual(sanitized.get("X-Custom"), "ok")

    def test_response_sanitization_removes_connection_tokens(self):
        headers = httpx.Headers(
            {
                "Connection": "X-Remove, keep-alive",
                "X-Remove": "value",
                "Keep-Alive": "timeout=5",
                "Content-Encoding": "gzip",
                "Content-Length": "999",
                "X-Custom": "ok",
            }
        )

        sanitized = _sanitize_response_headers(headers)
        names = [name.lower() for name, _ in sanitized]
        values_by_name: dict[str, list[str]] = {}
        for name, value in sanitized:
            values_by_name.setdefault(name.lower(), []).append(value)

        self.assertNotIn("x-remove", names)
        self.assertNotIn("keep-alive", names)
        self.assertNotIn("content-encoding", names)
        self.assertNotIn("content-length", names)
        self.assertEqual(values_by_name.get("x-custom"), ["ok"])

    def test_response_sanitization_preserves_repeated_headers(self):
        headers = httpx.Headers(
            [
                ("Vary", "Accept-Encoding"),
                ("Vary", "Origin"),
                ("Link", "<https://a.example>; rel=preload"),
                ("Link", "<https://b.example>; rel=preload"),
            ]
        )

        sanitized = _sanitize_response_headers(headers)
        vary_values = [value for name, value in sanitized if name.lower() == "vary"]
        link_values = [value for name, value in sanitized if name.lower() == "link"]

        self.assertEqual(vary_values, ["Accept-Encoding", "Origin"])
        self.assertEqual(
            link_values,
            [
                "<https://a.example>; rel=preload",
                "<https://b.example>; rel=preload",
            ],
        )


if __name__ == "__main__":
    unittest.main()
