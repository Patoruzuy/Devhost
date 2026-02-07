"""
Tests for input length limits (Phase 4 L-13).

Validates RFC 1035/1123 compliance for DNS names and labels.
"""

import unittest

from devhost_cli.router.security import (
    MAX_HOSTNAME_LENGTH,
    MAX_LABEL_LENGTH,
    validate_hostname,
)
from devhost_cli.router.security import (
    MAX_ROUTE_NAME_LENGTH as SECURITY_MAX_ROUTE_NAME,
)
from devhost_cli.validation import MAX_ROUTE_NAME_LENGTH, validate_name


class TestRouteLengthLimits(unittest.TestCase):
    """Test route name length limits (RFC 1035 compliance)."""

    def test_constants_match(self):
        """Test that length constants are consistent across modules."""
        self.assertEqual(MAX_ROUTE_NAME_LENGTH, 63)
        self.assertEqual(SECURITY_MAX_ROUTE_NAME, 63)
        self.assertEqual(MAX_LABEL_LENGTH, 63)
        self.assertEqual(MAX_HOSTNAME_LENGTH, 253)

    def test_max_route_name_valid(self):
        """Test that maximum length route name (63 chars) is accepted."""
        # Exactly 63 characters (RFC 1035 limit)
        name = "a" * 63
        self.assertTrue(validate_name(name))

    def test_route_name_too_long(self):
        """Test that route name exceeding 63 chars is rejected."""
        # 64 characters (exceeds RFC 1035 limit)
        name = "a" * 64
        self.assertFalse(validate_name(name))

    def test_route_name_edge_cases(self):
        """Test route name length edge cases."""
        # 62 chars - should pass
        self.assertTrue(validate_name("a" * 62))

        # 63 chars - should pass (exact limit)
        self.assertTrue(validate_name("a" * 63))

        # 64 chars - should fail
        self.assertFalse(validate_name("a" * 64))

        # 100 chars - should fail
        self.assertFalse(validate_name("a" * 100))

    def test_route_name_with_hyphens(self):
        """Test route name with hyphens at max length."""
        # Valid: 63 chars with hyphens
        name = "test-" + "a" * 54 + "-end"  # 5 + 54 + 4 = 63 chars
        self.assertEqual(len(name), 63)
        self.assertTrue(validate_name(name))

        # Invalid: 64 chars with hyphens
        name = "test-" + "a" * 55 + "-end"  # 5 + 55 + 4 = 64 chars
        self.assertEqual(len(name), 64)
        self.assertFalse(validate_name(name))

    def test_empty_name(self):
        """Test that empty name is rejected."""
        self.assertFalse(validate_name(""))

    def test_single_char_name(self):
        """Test that single character name is accepted."""
        self.assertTrue(validate_name("a"))


class TestHostnameLengthLimits(unittest.TestCase):
    """Test hostname length limits (RFC 1035/1123 compliance)."""

    def test_max_hostname_valid(self):
        """Test that maximum length hostname (253 chars) is accepted."""
        # Create a hostname with exactly 253 characters
        # Using labels of 63 chars each: 63.63.63.63 = 255 chars (too long)
        # Using labels of 62 chars each: 62.62.62.62 = 251 chars (OK)
        # Add 2 more chars: aa.62.62.62.62 = 253 chars (exact limit)
        # Total: 2 + 1 + 62 + 1 + 62 + 1 + 62 + 1 + 62 = 254 chars (too long by 1)

        # Better: use 5 labels of 50 chars each with dots
        # 50.50.50.50.50 = 254 chars (too long)
        # 50.50.50.50.49 = 253 chars (exact)
        parts = ["a" * 50, "b" * 50, "c" * 50, "d" * 50, "e" * 49]
        hostname = ".".join(parts)
        self.assertEqual(len(hostname), 253)

        is_valid, error = validate_hostname(hostname)
        self.assertTrue(is_valid, f"253-char hostname should be valid: {error}")

    def test_hostname_too_long(self):
        """Test that hostname exceeding 253 chars is rejected."""
        # 254 characters (exceeds RFC 1035 limit)
        parts = ["a" * 50, "b" * 50, "c" * 50, "d" * 50, "e" * 50]
        hostname = ".".join(parts)
        self.assertEqual(len(hostname), 254)

        is_valid, error = validate_hostname(hostname)
        self.assertFalse(is_valid)
        self.assertIn("253", error)  # Error should mention the limit
        self.assertIn("RFC 1035", error)  # Error should reference RFC

    def test_max_label_valid(self):
        """Test that maximum length label (63 chars) is accepted."""
        # Single label of exactly 63 characters
        hostname = "a" * 63 + ".example.com"

        is_valid, error = validate_hostname(hostname)
        self.assertTrue(is_valid, f"63-char label should be valid: {error}")

    def test_label_too_long(self):
        """Test that label exceeding 63 chars is rejected."""
        # Single label of 64 characters
        hostname = "a" * 64 + ".example.com"

        is_valid, error = validate_hostname(hostname)
        self.assertFalse(is_valid)
        self.assertIn("63", error)  # Error should mention the limit
        self.assertIn("RFC 1035", error)  # Error should reference RFC

    def test_label_edge_cases(self):
        """Test label length edge cases."""
        # 62 chars - should pass
        is_valid, _ = validate_hostname("a" * 62 + ".example.com")
        self.assertTrue(is_valid)

        # 63 chars - should pass (exact limit)
        is_valid, _ = validate_hostname("a" * 63 + ".example.com")
        self.assertTrue(is_valid)

        # 64 chars - should fail
        is_valid, _ = validate_hostname("a" * 64 + ".example.com")
        self.assertFalse(is_valid)

    def test_multiple_long_labels(self):
        """Test hostname with multiple max-length labels."""
        # Three 63-char labels with dots: 63.63.63 = 191 chars (valid)
        label1 = "a" * 63
        label2 = "b" * 63
        label3 = "c" * 63
        hostname = f"{label1}.{label2}.{label3}"

        is_valid, error = validate_hostname(hostname)
        self.assertTrue(is_valid, f"Multiple 63-char labels should be valid: {error}")

    def test_empty_hostname(self):
        """Test that empty hostname is rejected."""
        is_valid, error = validate_hostname("")
        self.assertFalse(is_valid)
        self.assertIn("empty", error.lower())

    def test_single_char_hostname(self):
        """Test that single character hostname is accepted."""
        is_valid, _ = validate_hostname("a")
        self.assertTrue(is_valid)


class TestRFCCompliance(unittest.TestCase):
    """Test RFC 1035/1123 compliance."""

    def test_rfc1035_section_2_3_4_label_limit(self):
        """Test RFC 1035 Section 2.3.4: labels must be 63 octets or less."""
        # Reference: https://datatracker.ietf.org/doc/html/rfc1035#section-2.3.4
        # "labels are restricted to 63 octets or less"

        # Exactly 63 octets (valid)
        is_valid, _ = validate_hostname("a" * 63)
        self.assertTrue(is_valid, "RFC 1035: 63-octet label should be valid")

        # 64 octets (invalid)
        is_valid, _ = validate_hostname("a" * 64)
        self.assertFalse(is_valid, "RFC 1035: 64-octet label should be invalid")

    def test_rfc1035_section_2_3_4_domain_name_limit(self):
        """Test RFC 1035 Section 2.3.4: domain names limited to 255 octets."""
        # Reference: https://datatracker.ietf.org/doc/html/rfc1035#section-2.3.4
        # Note: Practical limit is 253 (255 minus length byte and null terminator)

        # 253 octets (valid - practical limit)
        parts = ["a" * 50, "b" * 50, "c" * 50, "d" * 50, "e" * 49]
        hostname = ".".join(parts)
        self.assertEqual(len(hostname), 253)
        is_valid, _ = validate_hostname(hostname)
        self.assertTrue(is_valid, "RFC 1035: 253-octet domain should be valid")

        # 254 octets (invalid)
        parts = ["a" * 50, "b" * 50, "c" * 50, "d" * 50, "e" * 50]
        hostname = ".".join(parts)
        self.assertEqual(len(hostname), 254)
        is_valid, _ = validate_hostname(hostname)
        self.assertFalse(is_valid, "RFC 1035: 254-octet domain should be invalid")

    def test_dns_subdomain_as_route_name(self):
        """Test that route names follow DNS subdomain rules."""
        # Route names are used as DNS subdomains, so they must follow
        # the same rules as DNS labels (max 63 chars)

        # Valid route name (63 chars)
        self.assertTrue(validate_name("a" * 63))

        # Invalid route name (64 chars)
        self.assertFalse(validate_name("a" * 64))

    def test_error_messages_reference_rfc(self):
        """Test that error messages reference RFC standards."""
        # Hostname too long
        is_valid, error = validate_hostname("a" * 254)
        self.assertFalse(is_valid)
        self.assertIn("RFC 1035", error, "Error should reference RFC 1035")

        # Label too long
        is_valid, error = validate_hostname("a" * 64 + ".com")
        self.assertFalse(is_valid)
        self.assertIn("RFC 1035", error, "Error should reference RFC 1035")


class TestLengthLimitConstants(unittest.TestCase):
    """Test that length limit constants are properly defined."""

    def test_max_hostname_length_constant(self):
        """Test MAX_HOSTNAME_LENGTH constant."""
        self.assertEqual(MAX_HOSTNAME_LENGTH, 253)
        self.assertIsInstance(MAX_HOSTNAME_LENGTH, int)

    def test_max_label_length_constant(self):
        """Test MAX_LABEL_LENGTH constant."""
        self.assertEqual(MAX_LABEL_LENGTH, 63)
        self.assertIsInstance(MAX_LABEL_LENGTH, int)

    def test_max_route_name_length_constant(self):
        """Test MAX_ROUTE_NAME_LENGTH constant."""
        self.assertEqual(MAX_ROUTE_NAME_LENGTH, 63)
        self.assertIsInstance(MAX_ROUTE_NAME_LENGTH, int)

    def test_constants_are_powers_of_two_minus_one(self):
        """Test that 63 = 2^6 - 1 (fits in 6 bits with length encoding)."""
        # RFC 1035 uses 6 bits for label length (0-63)
        # This is why the limit is 63, not 64
        self.assertEqual(MAX_LABEL_LENGTH, 2**6 - 1)
        self.assertEqual(MAX_ROUTE_NAME_LENGTH, 2**6 - 1)


if __name__ == "__main__":
    unittest.main()
