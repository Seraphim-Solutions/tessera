import unittest

from tessera_2600.utils import validate_phone_number


class TestUtils(unittest.TestCase):
    def test_validate_phone_number_valid(self):
        self.assertTrue(validate_phone_number("+420 731x4x748"))
        self.assertTrue(validate_phone_number("+1 (202) 555-01xx"))
        self.assertTrue(validate_phone_number("+49 17xxxxxxxx"))

    def test_validate_phone_number_invalid(self):
        self.assertFalse(validate_phone_number("420 731x4x748"))  # missing plus
        self.assertFalse(validate_phone_number("+420-ABC-xxxx"))  # letters not allowed


if __name__ == '__main__':
    unittest.main()
