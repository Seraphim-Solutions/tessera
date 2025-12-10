import unittest
from unittest.mock import patch

from tessera_2600.core.descriptor_models import from_dict
from tessera_2600.core.declarative_service import DeclarativeService


class DummyResponse:
    def __init__(self, status_code=200, text="", json_obj=None):
        self.status_code = status_code
        self._text = text
        self._json = json_obj

    @property
    def text(self):
        return self._text

    def json(self):
        if self._json is None:
            raise ValueError("No JSON")
        return self._json


class TestDeclarativeService(unittest.TestCase):
    def setUp(self):
        # Minimal descriptor that confirms on 200 status with weight 1.0
        self.descriptor = from_dict({
            "schema_version": 1,
            "service_key": "dummy",
            "display_name": "Dummy",
            "requires_proxy": False,
            "timeouts": {"request": 5},
            "endpoints": [
                {
                    "name": "check",
                    "method": "GET",
                    "url": "https://example.com/check?phone=${phone}",
                    "success_signals": [
                        {"type": "status", "equals": 200, "weight": 1.0}
                    ],
                }
            ],
        })

    @patch("requests.Session.request")
    def test_confirms_on_success_signal(self, mock_request):
        mock_request.return_value = DummyResponse(status_code=200, json_obj={"ok": True})
        svc = DeclarativeService(self.descriptor)
        result = svc.check_phone_number("+420 731 234 567")
        self.assertIn("[FOUND]", result)

    @patch("requests.Session.request")
    def test_not_found_when_no_signals(self, mock_request):
        mock_request.return_value = DummyResponse(status_code=404, text="not found")
        svc = DeclarativeService(self.descriptor)
        result = svc.check_phone_number("+420 731 234 567")
        self.assertIn("[NOT FOUND]", result)


if __name__ == "__main__":
    unittest.main()
