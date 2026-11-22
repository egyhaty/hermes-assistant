"""Consent-gated OpenAI matching: one structured response, no tools or form answers."""
import json
import os
import urllib.error
import urllib.request

MODEL = 'gpt-6.2-sol'
SCHEMA = {'type': 'object', 'properties': {
    'eligible': {'type': 'boolean'}, 'reason': {'type': 'string'},
    'required_unknown': {'type': 'array', 'items': {'type': 'string'}},
    'gaps': {'type': 'array', 'items': {'type': 'string'}}},
    'required': ['eligible', 'reason', 'required_unknown', 'gaps'], 'additionalProperties': False}


def configuration_error():
    if os.environ.get('JOB_SCREENING_SHARING_APPROVED') != '1':
        return 'Professional-summary sharing has not been approved for OpenAI screening'
    if not os.environ.get('OPENAI_API_KEY'):
        return 'Connect the dedicated OpenAI API credential before enabling OpenAI screening'
    return None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OpenAIScreening:
    def invoke(self, instructions, prompt):
        error = configuration_error()
        if error:
            raise ValueError(error)
        payload = {'model': MODEL, 'store': False, 'service_tier': 'priority',
                   'reasoning': {'effort': 'low'}, 'max_output_tokens': 2048,
                   'instructions': instructions, 'input': prompt,
                   'text': {'format': {'type': 'json_schema', 'name': 'job_fit', 'strict': True, 'schema': SCHEMA}}}
        request = urllib.request.Request('https://api.openai.com/v1/responses', data=json.dumps(payload).encode(),
                                        headers={'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY'],
                                                 'Content-Type': 'application/json', 'User-Agent': 'hermes-job-matching/1.0'})
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=55) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            wrapped = RuntimeError('OpenAI screening returned HTTP ' + str(error.code) + '; no application was submitted')
            wrapped.status_code = error.code
            raise wrapped from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError('OpenAI screening connection failed; no application was submitted') from None
        if result.get('status') != 'completed':
            raise ValueError('OpenAI screening did not complete; manual review is required')
        text = []
        for output in result.get('output', []):
            if output.get('type') == 'message':
                for content in output.get('content', []):
                    if content.get('type') == 'refusal':
                        raise ValueError('OpenAI screening declined the request; manual review is required')
                    if content.get('type') == 'output_text':
                        text.append(content.get('text', ''))
        if len(text) != 1 or not text[0]:
            raise ValueError('OpenAI screening returned no unique structured decision')
        return text[0]
