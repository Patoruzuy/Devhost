"""Tests for validation module"""
import unittest

from devhost_cli.validation import parse_target, validate_ip, validate_name, validate_port


class ValidationTests(unittest.TestCase):
    def test_validate_name(self):
        # Valid names
        self.assertTrue(validate_name("hello"))
        self.assertTrue(validate_name("my-app"))
        self.assertTrue(validate_name("app123"))

        # Invalid names
        self.assertFalse(validate_name(""))
        self.assertFalse(validate_name("my_app"))  # underscore
        self.assertFalse(validate_name("my.app"))  # dot
        self.assertFalse(validate_name("a" * 64))  # too long

    def test_validate_port(self):
        # Valid ports
        self.assertTrue(validate_port(8000))
        self.assertTrue(validate_port(3000))
        self.assertTrue(validate_port(65535))

        # Invalid ports
        self.assertFalse(validate_port(0))
        self.assertFalse(validate_port(-1))
        self.assertFalse(validate_port(65536))

    def test_validate_ip(self):
        # Valid IPs
        self.assertTrue(validate_ip("127.0.0.1"))
        self.assertTrue(validate_ip("192.168.1.1"))
        self.assertTrue(validate_ip("10.0.0.1"))

        # Invalid IPs
        self.assertFalse(validate_ip("256.1.1.1"))
        self.assertFalse(validate_ip("192.168.1"))
        self.assertFalse(validate_ip("not.an.ip"))
        self.assertFalse(validate_ip(""))

    def test_parse_target(self):
        # Port only
        self.assertEqual(parse_target("3000"), ("http", "127.0.0.1", 3000))
        self.assertEqual(parse_target("8000"), ("http", "127.0.0.1", 8000))

        # host:port
        self.assertEqual(parse_target("127.0.0.1:8000"), ("http", "127.0.0.1", 8000))
        self.assertEqual(parse_target("localhost:3000"), ("http", "localhost", 3000))
        self.assertEqual(parse_target("192.168.1.100:8080"), ("http", "192.168.1.100", 8080))

        # Full URLs
        self.assertEqual(parse_target("http://127.0.0.1:8000"), ("http", "127.0.0.1", 8000))
        self.assertEqual(parse_target("https://example.com:8443"), ("https", "example.com", 8443))

        # Invalid
        self.assertIsNone(parse_target("bad"))
        self.assertIsNone(parse_target("host:bad"))
        self.assertIsNone(parse_target("0"))


if __name__ == "__main__":
    unittest.main()
