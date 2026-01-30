import unittest

from router.app import parse_target


class TargetParseTests(unittest.TestCase):
    def test_parse_target(self):
        self.assertEqual(parse_target(3000), ("127.0.0.1", 3000))
        self.assertEqual(parse_target("3000"), ("127.0.0.1", 3000))
        self.assertEqual(parse_target("127.0.0.1:8000"), ("127.0.0.1", 8000))
        self.assertIsNone(parse_target("bad"))
        self.assertIsNone(parse_target("host:bad"))
        self.assertIsNone(parse_target(0))


if __name__ == "__main__":
    unittest.main()