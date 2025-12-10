import unittest
from unittest.mock import patch

from tessera_2600.core import plugin_api
from tessera_2600.services import resolve_service_key
from tessera_2600.core.declarative_service import DeclarativeService


class TestPluginAPI(unittest.TestCase):
    def test_get_api_version(self):
        ver = plugin_api.get_api_version()
        self.assertIsInstance(ver, str)
        self.assertTrue(len(ver) > 0)

    def test_list_services_contains_builtin(self):
        services = plugin_api.list_services()
        # seznamcz is shipped as a descriptor in the repo
        self.assertIn('seznamcz', services)
        info = services['seznamcz']
        self.assertIn('name', info)
        self.assertEqual(info.get('origin'), 'builtin')

    def test_service_info_builtin(self):
        info = plugin_api.service_info('seznamcz')
        self.assertIsInstance(info, dict)
        self.assertEqual(info.get('origin'), 'builtin')
        self.assertEqual(info.get('name'), 'Seznam.cz')

    def test_create_service_instance(self):
        svc = plugin_api.create_service_instance('seznamcz', proxy_list=[], timeout=3)
        self.assertIsInstance(svc, DeclarativeService)
        self.assertEqual(svc.service_name, 'Seznam.cz')

    @patch.object(DeclarativeService, 'check_phone_number', return_value='[NOT FOUND] mocked')
    def test_check_phone_and_iter_check(self, _mock_method):
        # Single check
        res = plugin_api.check_phone('seznamcz', '+420 731 234 567')
        self.assertEqual(res.service, 'Seznam.cz')
        self.assertEqual(res.status, 'not_found')

        # Iterator check for multiple phones
        phones = ['+420 731 234 567', '+420 777 888 999']
        results = list(plugin_api.iter_check(phones, services_keys=['seznamcz'], proxy_list=[]))
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.status == 'not_found' for r in results))


if __name__ == '__main__':
    unittest.main()
