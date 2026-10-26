import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('pdf_report', Path(__file__).resolve().parents[1] / 'scripts/pdf_report.py')
pdf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdf)

class PdfReportTests(unittest.TestCase):
    def test_json_text_is_escaped(self):
        rendered = pdf.document({'title': '<script>alert(1)</script>', 'sections': [{'paragraphs': ['<img src="file:///etc/passwd">']}]})
        self.assertNotIn('<script>', rendered)
        self.assertNotIn('<img', rendered)
        self.assertIn('&lt;script&gt;', rendered)

    def test_mixed_content_has_explicit_first_strong_direction(self):
        self.assertEqual(pdf.text_dir("English with عربي"), "ltr")
        self.assertEqual(pdf.text_dir("العربية with English"), "rtl")
        rendered = pdf.document({"title": "Report", "sections": [{"paragraphs": ["English paragraph."]}]})
        self.assertIn('<p dir="ltr">English paragraph.</p>', rendered)
        self.assertIn("direction:ltr", pdf.CSS)

    def test_table_must_have_consistent_columns(self):
        with self.assertRaises(ValueError):
            pdf.document({'title': 'test', 'sections': [{'table': {'headers': ['a'], 'rows': [['a', 'b']]}}]})

    def test_resources_cannot_read_secrets_or_use_network(self):
        fake = types.SimpleNamespace(default_url_fetcher=lambda url: url)
        with tempfile.TemporaryDirectory() as root, patch.dict(sys.modules, {'weasyprint': fake}):
            assets = Path(root) / 'assets'
            assets.mkdir()
            secret = Path(root) / 'secret'
            secret.write_text('not a real secret')
            (assets / 'escape').symlink_to(secret)
            fetch = pdf.fetcher(assets)
            for url in ['https://example.com/a', 'http://127.0.0.1/', 'file:///etc/passwd', (assets / 'escape').as_uri(), (assets / '../secret').as_uri()]:
                with self.subTest(url=url), self.assertRaises(ValueError):
                    fetch(url)
            self.assertEqual(fetch((assets / 'logo.png').as_uri()), (assets / 'logo.png').resolve().as_uri())

    def test_sample_has_both_languages_and_two_sections(self):
        report = pdf.sample()
        self.assertTrue(report['sections'][1]['new_page'])
        rendered = pdf.document(report)
        self.assertIn('Technical verification', rendered)
        self.assertIn('العربية', rendered)

if __name__ == '__main__':
    unittest.main()
