import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'job-worker'))
from cdp_browser import allowed_url

class BrowserNavigationTests(unittest.TestCase):
 def test_navigation_stays_on_approved_job_board_hosts(self):
  for url in ('https://www.naukrigulf.com/jobs','https://profile.indeed.com/'):
   self.assertTrue(allowed_url(url))
  for url in ('http://www.naukrigulf.com/','https://www.naukrigulf.com.evil.test/','https://evilnaukrigulf.com/','https://user@www.naukrigulf.com/','https://www.naukrigulf.com:8443/'):
   self.assertFalse(allowed_url(url),url)
