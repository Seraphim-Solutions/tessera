import unittest

import tessera_2600.services as services


class TestDescriptorSelection(unittest.TestCase):
    def test_json_preferred_over_yaml(self):
        # Ensure the seznamcz service is registered
        self.assertIn("seznamcz", services.SERVICE_CONFIGURATIONS)

        cfg = services.SERVICE_CONFIGURATIONS["seznamcz"]
        # Descriptor file should be recorded and prefer JSON when both exist
        self.assertEqual(cfg.get("descriptor_file"), "seznamcz.json")

        src = services.get_descriptor_source("seznamcz")
        self.assertIsNotNone(src)
        self.assertEqual(src.get("selected_file"), "seznamcz.json")

        # Duplicate warnings should mention the service base name when both files exist
        dups = services.get_duplicate_warnings()
        self.assertTrue(any("seznamcz" in w for w in dups))


if __name__ == "__main__":
    unittest.main()
