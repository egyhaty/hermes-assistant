import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'job-worker' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load('job_sources')


class SourceTests(unittest.TestCase):
    def test_every_board_has_a_real_uae_search_route(self):
        for source in m.SOURCES:
            url = m.search_url(source, 'DevOps & Linux')
            self.assertTrue(url.startswith('https://'))
            self.assertIn(m.SOURCES[source]['host'], url)
            self.assertNotIn(' ', url)
        self.assertIn('geoId=104305776', m.search_url('linkedin', 'DevOps'))

    def test_invalid_source_or_term_cannot_become_an_arbitrary_fetch(self):
        for source, term in [('evil', 'jobs'), ('bayt', ''), ('bayt', 'x' * 101)]:
            with self.assertRaises(ValueError):
                m.search_url(source, term)

    def test_tracking_is_removed_and_job_identity_is_stable(self):
        self.assertEqual(m.canonical_url('linkedin', 'https://www.linkedin.com/jobs/view/devops-123456/?trackingId=x'),
                         'https://www.linkedin.com/jobs/view/123456/')
        self.assertEqual(m.canonical_url('indeed', '/viewjob?jk=abcdef1234&utm_source=test'),
                         'https://ae.indeed.com/viewjob?jk=abcdef1234')

    def test_external_urls_credentials_and_non_job_links_rejected(self):
        for url in ['https://linkedin.com.evil.test/jobs/view/1234', 'https://evil.test/jobs/view/1234',
                    'http://www.linkedin.com/jobs/view/1234', 'https://x@www.linkedin.com/jobs/view/1234',
                    'https://www.linkedin.com/feed/', 'javascript:alert(1)']:
            self.assertIsNone(m.canonical_url('linkedin', url))

    def test_redirect_cannot_fetch_internal_address(self):
        redirect = m.BoardRedirects('www.bayt.com')
        with self.assertRaises(ValueError):
            redirect.redirect_request(None, None, 302, '', {}, 'https://127.0.0.1/private')

    def test_linkedin_guest_cards_extract_company_and_location(self):
        html = '''<li><div class="base-card"><a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/devops-123456/"></a>
        <h3 class="base-search-card__title">DevOps Engineer</h3><h4 class="base-search-card__subtitle">Example</h4>
        <span class="job-search-card__location">Dubai, UAE</span></div></li>'''
        jobs = m.parse_jobs('linkedin', html)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['company'], 'Example')
        self.assertTrue(jobs[0]['location_verified'])
        self.assertEqual(jobs[0]['application_status'], 'not_applied')

    def test_structured_job_postings_on_each_board(self):
        paths = {'bayt': '/en/uae/jobs/devops-123456/', 'naukrigulf': '/devops-jobs-in-dubai-jid-123456',
                 'gulftalent': '/uae/jobs/devops-123456', 'indeed': '/viewjob?jk=abc123def4'}
        for source, path in paths.items():
            posting = {'@type': 'JobPosting', 'url': 'https://' + m.SOURCES[source]['host'] + path,
                       'title': 'Linux Engineer', 'hiringOrganization': {'name': 'Example'},
                       'jobLocation': {'address': {'addressLocality': 'Dubai', 'addressCountry': 'AE'}}}
            html = '<script type="application/ld+json">' + json.dumps({'@graph': [posting]}) + '</script>'
            jobs = m.parse_jobs(source, html)
            self.assertEqual(len(jobs), 1, source)
            self.assertTrue(jobs[0]['location_verified'])

    def test_unknown_or_foreign_location_is_never_promoted_to_uae(self):
        self.assertFalse(m.is_uae('Vancouver, BC'))
        self.assertFalse(m.is_uae(''))

    def test_403_is_reported_without_retry_or_submission(self):
        calls = []
        def blocked(req, timeout):
            calls.append(req.full_url)
            raise urllib.error.HTTPError(req.full_url, 403, 'Forbidden', {}, None)
        result = m.discover('bayt', 'DevOps', blocked)
        self.assertEqual(result['status'], 'action_required')
        self.assertEqual(len(calls), 1)
        self.assertEqual(result['jobs'], [])

    def test_unrecognised_html_is_not_claimed_as_successful_empty_search(self):
        result = m.discover('bayt', 'DevOps', lambda *a, **k: io.BytesIO(b'<html>Changed layout</html>'))
        self.assertEqual(result['status'], 'unrecognized')

    def test_duplicate_search_updates_seen_time_without_duplicate_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = m.Store(Path(tmp) / 'jobs.db')
            job = {'url': 'https://www.linkedin.com/jobs/view/123456/', 'source': 'linkedin',
                   'title': 'DevOps', 'application_status': 'not_applied'}
            result = {'source': 'linkedin', 'term': 'DevOps', 'jobs': [job], 'checked_at': 10}
            store.save(result)
            store.save(dict(result, checked_at=20))
            jobs = store.snapshot()['jobs']
            self.assertEqual(len(jobs), 1)
            self.assertEqual((jobs[0]['first_seen'], jobs[0]['last_seen']), (10, 20))
            history = Path(tmp) / 'history.csv'
            history.write_text('Job ID,Job Link,Date Applied\n123456,,Pending\n')
            self.assertEqual(store.snapshot(history)['jobs'][0]['application_status'], 'recorded_in_legacy_history')


class LinkedInCompatibilityTests(unittest.TestCase):
    def test_navigation_has_explicit_location_and_easy_apply(self):
        compat = load('linkedin_compat')
        url = compat.search_url('Linux & DevOps', 'United Arab Emirates')
        self.assertIn('geoId=104305776', url)
        self.assertIn('f_AL=true', url)
        with self.assertRaises(ValueError):
            compat.search_url('DevOps', '')

    def test_timeout_is_not_a_closed_browser(self):
        compat = load('linkedin_compat')
        timeout = type('TimeoutException', (Exception,), {})()
        self.assertIn('layout changed', compat.failure_reason(timeout))
        self.assertNotIn('window closed', compat.failure_reason(timeout))
        self.assertEqual(compat.failure_reason(compat.LinkedInLayoutChanged('layout unsupported')), 'layout unsupported')
