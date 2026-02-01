"""Tests for router utils module"""

import os
import unittest

from devhost_cli.router.utils import extract_subdomain, load_domain, parse_target


class UtilsTests(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.default_domain_env = os.getenv("DEVHOST_DOMAIN", "")

    def tearDown(self):
        """Clean up test environment"""
        if self.default_domain_env:
            os.environ["DEVHOST_DOMAIN"] = self.default_domain_env
        elif "DEVHOST_DOMAIN" in os.environ:
            del os.environ["DEVHOST_DOMAIN"]

    def test_load_domain_from_env(self):
        """Test loading domain from DEVHOST_DOMAIN env var"""
        os.environ["DEVHOST_DOMAIN"] = "example.com"
        self.assertEqual(load_domain(), "example.com")

    def test_load_domain_defaults_to_localhost(self):
        """Test default domain is localhost"""
        if "DEVHOST_DOMAIN" in os.environ:
            del os.environ["DEVHOST_DOMAIN"]
        self.assertEqual(load_domain(), "localhost")

    def test_load_domain_strips_whitespace(self):
        """Test domain is stripped of whitespace"""
        os.environ["DEVHOST_DOMAIN"] = "  example.com  "
        self.assertEqual(load_domain(), "example.com")

    def test_load_domain_lowercases(self):
        """Test domain is lowercased"""
        os.environ["DEVHOST_DOMAIN"] = "EXAMPLE.COM"
        self.assertEqual(load_domain(), "example.com")

    def test_extract_subdomain_with_port(self):
        """Test extracting subdomain when host includes port"""
        subdomain = extract_subdomain("hello.localhost:8000", "localhost")
        self.assertEqual(subdomain, "hello")

    def test_extract_subdomain_none_host(self):
        """Test None host returns None"""
        self.assertIsNone(extract_subdomain(None, "localhost"))

    def test_extract_subdomain_no_match(self):
        """Test non-matching domain returns None"""
        self.assertIsNone(extract_subdomain("example.com", "localhost"))

    def test_extract_subdomain_exact_match(self):
        """Test exact domain match (no subdomain) returns None"""
        self.assertIsNone(extract_subdomain("localhost", "localhost"))

    def test_extract_subdomain_multiple_levels(self):
        """Test multi-level subdomains"""
        subdomain = extract_subdomain("api.v2.localhost", "localhost")
        self.assertEqual(subdomain, "api.v2")

    def test_extract_subdomain_case_insensitive(self):
        """Test subdomain extraction is case-insensitive"""
        subdomain = extract_subdomain("HELLO.LOCALHOST", "localhost")
        self.assertEqual(subdomain, "hello")

    def test_parse_target_integer(self):
        """Test parsing integer port"""
        result = parse_target(8080)
        self.assertEqual(result, ("http", "127.0.0.1", 8080))

    def test_parse_target_zero_port(self):
        """Test zero port returns None"""
        self.assertIsNone(parse_target(0))

    def test_parse_target_negative_port(self):
        """Test negative port returns None"""
        self.assertIsNone(parse_target(-1))

    def test_parse_target_string_port(self):
        """Test parsing string port"""
        result = parse_target("8080")
        self.assertEqual(result, ("http", "127.0.0.1", 8080))

    def test_parse_target_host_port(self):
        """Test parsing host:port string"""
        result = parse_target("192.168.1.100:8080")
        self.assertEqual(result, ("http", "192.168.1.100", 8080))

    def test_parse_target_localhost_with_port(self):
        """Test parsing localhost:port"""
        result = parse_target("localhost:3000")
        self.assertEqual(result, ("http", "localhost", 3000))

    def test_parse_target_full_http_url(self):
        """Test parsing full HTTP URL"""
        result = parse_target("http://example.com:8080")
        self.assertEqual(result, ("http", "example.com", 8080))

    def test_parse_target_full_https_url(self):
        """Test parsing full HTTPS URL"""
        result = parse_target("https://example.com:443")
        self.assertEqual(result, ("https", "example.com", 443))

    def test_parse_target_url_without_port(self):
        """Test URL without port returns None"""
        self.assertIsNone(parse_target("http://example.com"))

    def test_parse_target_invalid_host_port(self):
        """Test invalid host:port returns None"""
        self.assertIsNone(parse_target("example.com:abc"))

    def test_parse_target_none(self):
        """Test None target returns None"""
        self.assertIsNone(parse_target(None))

    def test_parse_target_empty_string(self):
        """Test empty string returns None"""
        self.assertIsNone(parse_target(""))

    def test_parse_target_ipv6_with_port(self):
        """Test IPv6 address with port (not currently supported)"""
        # This should fail gracefully
        parse_target("[::1]:8080")
        # Current implementation won't parse this correctly
        # This test documents current behavior


if __name__ == "__main__":
    unittest.main()
