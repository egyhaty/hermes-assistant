import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'job-worker'))
from gpt_matcher import Matcher, create_app, client_failure


class GPTServiceTests(unittest.TestCase):
    def test_model_diagnostic_is_useful_without_raw_account_details(self):
        error=json.dumps({'type':'error','message':json.dumps({'error':{'code':'model_not_found','message':'private@example.test account detail'}})})
        message=client_failure(error)
        self.assertIn('model',message);self.assertNotIn('private@example.test',message)

    def test_successful_decision_survives_non_tool_startup_diagnostic(self):
        class Process:
            returncode = 0
            def __init__(inner, argv, **kwargs):
                inner.output = Path(argv[argv.index('--output-last-message')+1])
            def communicate(inner, prompt, timeout):
                inner.output.write_text(json.dumps({'eligible':True,'reason':'Linux match','required_unknown':[],'gaps':[]}))
                return json.dumps({'item':{'type':'error','message':'startup diagnostic'}}), ''
        with patch.object(self.matcher,'connected',return_value=True),patch('gpt_matcher.subprocess.Popen',side_effect=Process):
            self.assertTrue(self.matcher.match('synthetic professional facts')['eligible'])
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.matcher = Matcher(self.tmp.name)

    def test_child_does_not_inherit_server_credentials(self):
        with patch.dict(os.environ, {'GPT_MATCHER_TOKEN': 'private', 'GROQ_API_KEY': 'private', 'CONTROL_TOKEN': 'private', 'OPENAI_API_KEY': 'private'}):
            env = self.matcher.env()
        for key in ('GPT_MATCHER_TOKEN', 'GROQ_API_KEY', 'CONTROL_TOKEN', 'OPENAI_API_KEY'):
            self.assertNotIn(key, env)
        self.assertEqual(env['CODEX_HOME'], self.tmp.name)

    def test_client_keeps_sandbox_and_disables_command_web_and_account_tools(self):
        argv = self.matcher.command(self.tmp.name)
        self.assertIn('read-only', argv); self.assertIn('--ephemeral', argv)
        for setting in ('features.shell_tool=false', 'features.multi_agent=false', 'apps._default.enabled=false', 'web_search="disabled"', 'mcp_servers={}'): self.assertIn(setting, argv)
        self.assertFalse(any('bypass' in arg for arg in argv))

    def test_disconnected_account_cannot_start_model_request(self):
        with patch.object(self.matcher, 'connected', return_value=False), patch('gpt_matcher.subprocess.Popen') as popen:
            with self.assertRaises(ValueError): self.matcher.match('professional summary')
            popen.assert_not_called()

    def test_concurrent_matches_are_refused(self):
        self.matcher.busy.acquire()
        try:
            with patch.object(self.matcher, 'connected', return_value=True), patch('gpt_matcher.subprocess.Popen') as popen:
                with self.assertRaises(ValueError): self.matcher.match('professional summary')
                popen.assert_not_called()
        finally: self.matcher.busy.release()

    def test_inference_does_not_execute_a_tool_turn(self):
        owner = self
        class Process:
            returncode = 0
            def communicate(self, prompt, timeout):
                return json.dumps({'item': {'type': 'command_execution'}}), ''
        with patch.object(self.matcher, 'connected', return_value=True), patch('gpt_matcher.subprocess.Popen', return_value=Process()):
            with self.assertRaisesRegex(ValueError, 'unexpected tool'): self.matcher.match('professional summary')
        self.assertFalse(self.matcher.busy.locked())


class GPTHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.token = patch.dict(os.environ, {'GPT_MATCHER_TOKEN': 'unit-test-token'}); self.token.start()
        self.client = TestClient(TestServer(create_app(self.tmp.name))); await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close(); self.token.stop(); self.tmp.cleanup()

    async def test_unauthenticated_client_cannot_read_login_codes(self):
        response = await self.client.get('/status'); self.assertEqual(response.status, 401)

    async def test_unauthenticated_client_cannot_start_login_or_inference(self):
        with patch('gpt_matcher.Matcher.connect') as connect, patch('gpt_matcher.Matcher.match') as match:
            self.assertEqual((await self.client.post('/connect')).status, 401)
            self.assertEqual((await self.client.post('/match', json={'prompt': 'example'})).status, 401)
            connect.assert_not_called(); match.assert_not_called()

    async def test_health_does_not_claim_authenticated_matching(self):
        response = await self.client.get('/health'); self.assertEqual(response.status, 200)
        data = await response.json(); self.assertNotIn('connected', data); self.assertTrue(data['service_ready'])

    async def test_login_state_requires_the_private_control_token(self):
        with patch('gpt_matcher.Matcher.status', return_value={'connected': False, 'login_pending': False}):
            response = await self.client.get('/status', headers={'Authorization': 'Bearer unit-test-token'})
            self.assertEqual(response.status, 200); self.assertFalse((await response.json())['connected'])
