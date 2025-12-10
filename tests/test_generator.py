import unittest

from tessera_2600.generator import validate_pattern, expand_phone_number
from tessera_2600.config import MAX_WILDCARDS


class TestGenerator(unittest.TestCase):
    def test_validate_pattern_ok(self):
        self.assertTrue(validate_pattern("+420 731x4x748"))

    def test_validate_pattern_requires_wildcard(self):
        self.assertFalse(validate_pattern("+420 731444748"))

    def test_validate_pattern_excessive_wildcards(self):
        pattern = "+420 " + ("x" * (MAX_WILDCARDS + 1))
        self.assertFalse(validate_pattern(pattern))

    def test_expand_phone_number_basic(self):
        out = expand_phone_number("+1 23x", use_country_prefixes=False)
        self.assertEqual(len(out), 10)
        self.assertIn("+1 230", out)
        self.assertIn("+1 239", out)


if __name__ == '__main__':
    unittest.main()
