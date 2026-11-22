import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'job-worker'))
from application_journal import Journal
from job_reports import applications_csv, summary, dubai_time


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.journal = Journal(Path(self.tmp.name) / 'journal.db')
        self.job = {'source': 'naukrigulf', 'url': 'https://www.naukrigulf.com/linux-jobs-in-dubai-jid-123456',
                    'title': '=untrusted_formula()', 'company': 'Example', 'location': 'Dubai'}

    def test_discovery_and_skips_are_not_counted_as_confirmed_submissions(self):
        self.journal.review(self.job, 'a' * 64, False, 'A required skill is missing')
        result = summary(self.journal)
        self.assertEqual(result['counts'].get('confirmed', 0), 0)
        self.assertEqual(result['counts']['skipped'], 1)

    def test_export_neutralises_spreadsheet_formulas(self):
        self.journal.review(self.job, 'a' * 64, False, 'Skipped')
        rows = list(csv.reader(io.StringIO(applications_csv(self.journal).lstrip('\ufeff'))))
        self.assertEqual(rows[1][rows[0].index('Role')], "'=untrusted_formula()")

    def test_dubai_date_does_not_use_host_timezone(self):
        self.assertEqual(dubai_time(0), '')
        self.assertEqual(dubai_time(86400), '1970-01-02T04:00:00+04:00')

    def test_cancelled_run_cannot_be_overwritten_as_completed(self):
        key = 'a' * 32
        self.journal.start_run(key, 'naukrigulf', 'codex')
        self.journal.finish_run(key, 'cancelled', {'confirmed': 0}, 'Stopped')
        self.journal.finish_run(key, 'completed', {'confirmed': 1}, 'Done')
        result = self.journal.run_history()[0]
        self.assertEqual(result['status'], 'cancelled'); self.assertEqual(result['counts']['confirmed'], 0)

    def test_restart_preserves_attempts_as_uncertain_without_reopening_them(self):
        self.journal.review(self.job, 'a' * 64, True, 'Reviewed')
        self.assertTrue(self.journal.claim(self.job['url'], 'a' * 64))
        self.journal.start_run('b' * 32, 'naukrigulf', 'codex')
        self.journal.recover_interrupted_runs()
        self.assertEqual(self.journal.snapshot()[0]['status'], 'uncertain')
        self.assertFalse(self.journal.claim(self.job['url'], 'a' * 64))
        self.assertEqual(self.journal.run_history()[0]['status'], 'interrupted')

    def test_gpt_can_reconsider_an_unattempted_rule_based_rejection(self):
        old = dict(self.job, screening={'eligible': False})
        self.journal.review(old, 'a' * 64, False, 'Rule requires review')
        self.assertNotIn(old['url'], self.journal.known_urls('codex'))
        new = dict(self.job, screening={'eligible': True, 'provider': 'codex'})
        self.assertEqual(self.journal.review(new, 'a' * 64, True, 'GPT reviewed requirements'), 'eligible')
        self.assertTrue(self.journal.claim(new['url'], 'a' * 64))

    def test_matcher_change_never_reopens_an_uncertain_submission(self):
        old = dict(self.job, screening={'eligible': True, 'provider': 'local'})
        self.journal.review(old, 'a' * 64, True, 'Reviewed'); self.journal.claim(old['url'], 'a' * 64)
        self.journal.finish(old['url'], 'uncertain', 'Platform confirmation absent')
        new = dict(self.job, screening={'eligible': True, 'provider': 'codex'})
        self.assertIn(new['url'], self.journal.known_urls('codex'))
        self.assertEqual(self.journal.review(new, 'a' * 64, True, 'GPT reviewed'), 'uncertain')
