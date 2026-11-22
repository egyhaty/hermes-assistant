import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'job-worker'))
from job_matching import professional_facts, screen
from openai_screening import OpenAIScreening, MODEL


class Response:
    def __init__(self, value): self.value = value
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return json.dumps(self.value).encode()


class OpenAIScreeningTests(unittest.TestCase):
    def config(self):
        return {'personals': {'phone_number': '0501234567'}, 'questions': {'user_information_all':
            'Professional Summary\nLinux production operations.\nDevOps Project\nKubernetes GitOps lab.\n'
            'Technical Skills\nLinux, DNS, backups\nProfessional Experience\n'
            'Certification and Education\nCKA; Social Work degree\nBoundary: AWS labs are not production years.\n'
            'Owner-confirmed: UAE investor residency; notice period 0; work permit not confirmed.'}}

    def completed(self, text):
        return {'status': 'completed', 'output': [{'type': 'reasoning'}, {'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]}

    def test_no_consent_means_no_outbound_request(self):
        with patch.dict(os.environ, {'JOB_SCREENING_SHARING_APPROVED': '0', 'OPENAI_API_KEY': 'test'}, clear=False), patch('urllib.request.build_opener') as opener:
            with self.assertRaises(ValueError): OpenAIScreening().invoke('system', 'profile')
            opener.assert_not_called()

    def test_no_key_means_no_outbound_request(self):
        with patch.dict(os.environ, {'JOB_SCREENING_SHARING_APPROVED': '1', 'OPENAI_API_KEY': ''}, clear=False), patch('urllib.request.build_opener') as opener:
            with self.assertRaises(ValueError): OpenAIScreening().invoke('system', 'profile')
            opener.assert_not_called()

    def test_request_uses_strict_schema_low_reasoning_and_no_storage_or_tools(self):
        raw = '{"eligible":true,"reason":"Core Linux fit","required_unknown":[],"gaps":[]}'
        with patch.dict(os.environ, {'JOB_SCREENING_SHARING_APPROVED': '1', 'OPENAI_API_KEY': 'test-key'}, clear=False), patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = Response(self.completed(raw))
            self.assertEqual(OpenAIScreening().invoke('instructions', 'professional facts'), raw)
            req = opener.return_value.open.call_args[0][0]
            body = json.loads(req.data)
            self.assertEqual(req.full_url, 'https://api.openai.com/v1/responses')
            self.assertEqual(body['model'], MODEL)
            self.assertFalse(body['store']); self.assertTrue(body['text']['format']['strict'])
            self.assertEqual(body['reasoning']['effort'], 'low')
            self.assertEqual(body['service_tier'], 'priority'); self.assertNotIn('tools', body)

    def test_incomplete_response_cannot_become_a_positive_decision(self):
        with patch.dict(os.environ, {'JOB_SCREENING_SHARING_APPROVED': '1', 'OPENAI_API_KEY': 'test'}, clear=False), patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = Response({'status': 'incomplete', 'output': []})
            with self.assertRaises(ValueError): OpenAIScreening().invoke('system', 'professional facts')

    def test_refusal_is_not_a_fit_decision(self):
        with patch.dict(os.environ, {'JOB_SCREENING_SHARING_APPROVED': '1', 'OPENAI_API_KEY': 'test'}, clear=False), patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = Response({'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal'}]}]})
            with self.assertRaises(ValueError): OpenAIScreening().invoke('system', 'professional facts')

    def test_only_approved_professional_sections_leave_the_worker(self):
        c = self.config()
        c['questions']['user_information_all'] = c['questions']['user_information_all'].replace('Linux production', '0501234567 test@example.test +1 (202) 555-0199 Linux production')
        facts = json.dumps(professional_facts(c))
        for private in ('0501234567', 'test@example.test', '+1 (202) 555-0199', 'investor', 'notice period', 'work permit'):
            self.assertNotIn(private, facts)
        self.assertIn('not production years', facts)

    def test_openai_mode_never_falls_back_to_groq(self):
        with patch.dict(os.environ, {'JOB_SCREENING_MODE': 'openai'}, clear=False), patch('openai_screening.OpenAIScreening.invoke') as invoke, patch('job_matching.FreePlanScreening.invoke') as groq:
            invoke.return_value = '{"eligible":true,"reason":"Unknown prerequisite","required_unknown":["Mandatory skill not verified"],"gaps":[]}'
            d = screen(self.config(), {'title': 'Linux Administrator', 'company': 'Example', 'head': 'SIGNED-IN OWNER\nLinux Administrator\nDubai, UAE\nJob Description\nRepeated body', 'description': 'Maintain Linux servers.'})
            self.assertFalse(d['eligible']); groq.assert_not_called()
            prompt = json.loads(invoke.call_args[0][1])
            self.assertNotIn('SIGNED-IN OWNER', prompt['job']['head'])
            self.assertNotIn('Repeated body', prompt['job']['head'])
            self.assertIn('Dubai', prompt['job']['head'])

    def test_unknown_mode_fails_without_any_provider_request(self):
        with patch.dict(os.environ, {'JOB_SCREENING_MODE': 'typo'}, clear=False), patch('job_matching.FreePlanScreening.invoke') as groq:
            with self.assertRaises(ValueError): screen(self.config(), {})
            groq.assert_not_called()
