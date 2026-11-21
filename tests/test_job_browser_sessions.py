import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'job-worker'))
from browser_sessions import open_board


class BrowserSessionsTests(unittest.TestCase):
    def opener(self, pages):
        self.requests = []
        def call(request, timeout):
            url = request if isinstance(request, str) else request.full_url
            self.requests.append((url, getattr(request, 'method', 'GET')))
            return io.BytesIO(json.dumps(pages if url.endswith('/json') else {}).encode())
        return call

    def test_existing_session_is_activated_without_opening_duplicate_tabs(self):
        result = open_board('indeed', self.opener([{'type': 'page', 'id': 'existing-tab', 'url': 'https://profile.indeed.com/'}]))
        self.assertTrue(result['reused'])
        self.assertEqual(self.requests[-1][0], 'http://127.0.0.1:9222/json/activate/existing-tab')
        self.assertFalse(any('/json/new' in url for url, _ in self.requests))

    def test_unrelated_host_cannot_be_mistaken_for_a_signed_in_board(self):
        result = open_board('linkedin', self.opener([{'type': 'page', 'id': 'evil', 'url': 'https://evillinkedin.com/'}]))
        self.assertFalse(result['reused'])
        self.assertEqual(self.requests[-1][1], 'PUT')
        self.assertIn('https%3A%2F%2Fwww.linkedin.com%2F', self.requests[-1][0])

    def test_invalid_target_id_is_not_used_as_a_loopback_path(self):
        result = open_board('bayt', self.opener([{'type': 'page', 'id': '../json/close/x', 'url': 'https://www.bayt.com/'}]))
        self.assertFalse(result['reused'])

    def test_unknown_board_is_rejected_before_any_browser_call(self):
        with self.assertRaises(ValueError):
            open_board('unknown', lambda *a, **k: self.fail('Unexpected request'))
