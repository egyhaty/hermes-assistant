import base64
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from configure_free_api import dashboard_password_hash


class DashboardCredentialTests(unittest.TestCase):
    def test_password_only_goes_to_stdin_and_uses_runtime_hash(self):
        password = 'test-only-secret-password'
        encoded = 'scrypt$16384$8$1$' + base64.b64encode(b's' * 16).decode() + '$' + base64.b64encode(b'h' * 32).decode()
        with patch('configure_free_api.subprocess.run', return_value=subprocess.CompletedProcess([], 0, encoded + '\n', '')) as run:
            self.assertEqual(dashboard_password_hash('fixture-context', password), encoded)
        args, kwargs = run.call_args
        self.assertNotIn(password, ' '.join(args[0]))
        self.assertEqual(kwargs['input'], password)
        self.assertNotIn('hashlib.scrypt', args[0])

    def test_failure_does_not_disclose_stdout_stderr_or_password(self):
        with patch('configure_free_api.subprocess.run', return_value=subprocess.CompletedProcess([], 1, 'private stdout', 'private stderr')):
            with self.assertRaises(SystemExit) as result:
                dashboard_password_hash('fixture-context', 'private password')
        self.assertNotIn('private', str(result.exception))

    def test_malformed_hash_is_refused(self):
        with patch('configure_free_api.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'not-a-scrypt-hash', '')):
            with self.assertRaises(SystemExit):
                dashboard_password_hash('fixture-context', 'test password')
