import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'job-worker'))
from application_journal import Journal
from application_answers import is_resume_field
from board_adapter import first_party_application
from application_context import require_reviewed_page
from cdp_browser import BrowserPage
from job_matching import scope_error
import browser_application_form as forms
import multisite_worker as batch
import linkedin_adapter as linkedin


class ScopeAndBoundaryTests(unittest.TestCase):
    def test_dom_readiness_is_coerced_before_cdp_serializes_a_node(self):
        page = BrowserPage.__new__(BrowserPage)
        def evaluate(expression):
            if not expression.startswith('!!('): raise RuntimeError('Object reference chain is too long')
            return True
        page.js = evaluate
        self.assertTrue(page.wait("document.querySelector('main')"))
    def test_worldwide_hosting_and_uae_remote_are_within_scope(self):
        for location in ('Remote worldwide', 'Work remotely from the UAE'):
            self.assertIsNone(scope_error({'title': 'Linux Hosting Support Engineer', 'head': location}, 'hosting_remote'))

    def test_remote_without_country_eligibility_and_us_only_are_held(self):
        for location in ('Remote, location unspecified', 'Remote US-only; must reside in the United States'):
            self.assertTrue(scope_error({'title': 'Linux Hosting Support Engineer', 'head': location}, 'hosting_remote'))

    def test_attachment_type_is_not_guessed(self):
        self.assertTrue(is_resume_field({'label': 'Upload resume'}))
        self.assertTrue(is_resume_field({'originalId': 'jobs-document-upload-file-upload'}))
        for label in ('Upload passport', 'Resume cover letter', 'Required license document'):
            self.assertFalse(is_resume_field({'label': label}))

    def test_first_party_requires_exact_domain_boundary_and_https(self):
        self.assertTrue(first_party_application('indeed', 'https://smartapply.indeed.com/apply/'))
        for url in ('https://evilindeed.com/', 'http://ae.indeed.com/', 'https://a@ae.indeed.com/', 'https://ae.indeed.com:8443/'):
            self.assertFalse(first_party_application('indeed', url))


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.resume = self.root / 'resume.pdf'; self.resume.write_bytes(b'%PDF-1.7\nfixture')
        self.digest = hashlib.sha256(self.resume.read_bytes()).hexdigest()
        self.journal = Journal(self.root / 'journal.db')
        self.job = {'source': 'linkedin', 'url': 'https://www.linkedin.com/jobs/view/123456/', 'title': 'Linux Engineer', 'easyApply': True, 'alreadyApplied': False}
        self.journal.review(self.job, self.digest, True, 'Verified Linux role')

    def test_unknown_required_form_gets_no_final_submit(self):
        class Page:
            def wait(self, *args): return True
            def js(self, code):
                return {'missing': False, 'text': 'Application', 'fields': [{'id': 'field-0', 'type': 'text', 'label': 'Production Azure years', 'question': 'Production Azure years', 'required': True, 'value': '10'}], 'buttons': [{'label': 'Submit application', 'disabled': False}], 'errors': []}
        with patch.object(forms, 'DATA', self.root), patch.object(forms, '_click') as click:
            result = forms.complete_form(Page(), {'personals': {}, 'questions': {}}, self.resume, self.digest)
            self.assertEqual(result['status'], 'needs_input'); click.assert_not_called()

    def test_browser_navigation_cannot_redirect_an_approved_application(self):
        class Page:
            def js(self, code): return 'https://www.linkedin.com/jobs/view/999999/'
        with self.assertRaisesRegex(RuntimeError, 'left the reviewed job'):
            require_reviewed_page(Page(), self.job)
        self.assertEqual(self.journal.snapshot()[0]['attempts'], 0)

    def test_new_cv_can_reconsider_a_rejection_but_never_a_previous_attempt(self):
        self.journal.review(dict(self.job, url='https://www.linkedin.com/jobs/view/123457/', screening={'provider': 'codex'}), 'a'*64, False, 'Old CV needs review')
        url = 'https://www.linkedin.com/jobs/view/123457/'
        self.assertNotIn(url, self.journal.known_urls('codex', self.digest))
        self.assertEqual(self.journal.review(dict(self.job, url=url, screening={'provider': 'codex'}), self.digest, True, 'New reviewed CV fits'), 'eligible')
        self.journal.claim(self.job['url'], self.digest); self.journal.finish(self.job['url'], 'uncertain', 'No receipt')
        self.assertIn(self.job['url'], self.journal.known_urls('codex', 'b'*64))

    def test_success_modal_without_persisted_applied_state_is_not_confirmed(self):
        class Page:
            def js(inner, code): return self.job['url'] if code == 'location.href' else True
        with patch.object(forms, 'complete_form', return_value={'status': 'sent', 'evidence': 'Application sent'}), patch.object(linkedin, 'inspect_job', return_value={'alreadyApplied': False}):
            self.assertEqual(linkedin.submit(Page(), self.job, self.journal, self.digest, {}, self.resume), 'uncertain')
        self.assertEqual(self.journal.counts().get('confirmed', 0), 0)

    def test_cv_sync_digest_must_match_before_source_is_enabled(self):
        (self.root/'reviewed-cv-sync.json').write_text(json.dumps({'sites': [{'source': 'linkedin', 'persisted': True, 'sha256': 'a'*64}]}))
        with patch.object(batch, 'DATA', self.root): self.assertTrue(batch.cv_sync_error('linkedin'))
