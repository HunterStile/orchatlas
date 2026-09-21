import io
import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from orchatlas.clients import verify_openrouter_key


class ConnectionTests(unittest.TestCase):
    def test_effective_key_is_validated_at_openrouter_and_only_status_is_returned(self):
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = json.dumps({
            "data": {"label": "private-label", "creator_user_id": "private-account", "limit_remaining": None}}).encode()
        with patch("orchatlas.clients.urllib.request.build_opener", return_value=opener):
            result = verify_openrouter_key("synthetic-key")
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://openrouter.ai/api/v1/key")
        self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-key")
        self.assertEqual(result, {"valid": True})

    def test_rejected_key_is_redacted_and_points_to_the_correct_provider(self):
        opener = MagicMock()
        opener.open.side_effect = HTTPError("https://openrouter.ai/api/v1/key", 401,
                                           "synthetic-secret", {}, io.BytesIO(b"synthetic-secret"))
        with patch("orchatlas.clients.urllib.request.build_opener", return_value=opener):
            result = verify_openrouter_key("synthetic-key")
        self.assertFalse(result["valid"])
        self.assertIn("/login openrouter", result["reason"])
        self.assertNotIn("synthetic", str(result))

    def test_network_failure_is_not_reported_as_an_invalid_key_or_valid_connection(self):
        opener = MagicMock()
        opener.open.side_effect = OSError("private proxy details")
        with patch("orchatlas.clients.urllib.request.build_opener", return_value=opener):
            result = verify_openrouter_key("synthetic-key")
        self.assertFalse(result["valid"])
        self.assertIn("network", result["reason"])
        self.assertNotIn("private", str(result))

    def test_key_spending_limit_and_management_keys_cannot_start_worker(self):
        for data in ({"limit_remaining": 0}, {"is_management_key": True}):
            with self.subTest(data=data):
                opener = MagicMock()
                opener.open.return_value.__enter__.return_value.read.return_value = json.dumps({"data": data}).encode()
                with patch("orchatlas.clients.urllib.request.build_opener", return_value=opener):
                    self.assertFalse(verify_openrouter_key("synthetic-key")["valid"])
