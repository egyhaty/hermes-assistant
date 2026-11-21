import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'job-worker'))
from application_journal import Journal

class ApplicationJournalTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.j=Journal(Path(self.tmp.name)/'applications.db')
  self.url='https://www.naukrigulf.com/linux-jobs-in-dubai-jid-123456'
  self.job={'source':'naukrigulf','url':self.url,'title':'Linux Administrator'}
  self.digest='a'*64
 def test_two_workers_cannot_claim_the_same_submission(self):
  self.j.review(self.job,self.digest,True,'Verified Linux role in UAE')
  self.assertTrue(self.j.claim(self.url,self.digest));self.assertFalse(self.j.claim(self.url,self.digest))
 def test_changed_cv_cannot_use_a_stale_review(self):
  self.j.review(self.job,self.digest,True,'Reviewed against this CV')
  self.assertFalse(self.j.claim(self.url,'b'*64))
 def test_uncertain_attempt_is_not_retried_after_restart(self):
  self.j.review(self.job,self.digest,True,'Reviewed role');self.j.claim(self.url,self.digest)
  self.j.finish(self.url,'uncertain','Platform did not confirm')
  restarted=Journal(self.j.path);self.assertEqual(restarted.review(self.job,self.digest,True,'Revisited role'),'uncertain')
  self.assertFalse(restarted.claim(self.url,self.digest))
 def test_confirmation_requires_evidence_and_an_attempt(self):
  self.j.review(self.job,self.digest,True,'Reviewed role');self.j.claim(self.url,self.digest)
  with self.assertRaises(ValueError):self.j.finish(self.url,'confirmed','Submitted')
  self.j.finish(self.url,'confirmed','Platform acknowledged','Application submitted successfully')
  self.assertEqual(self.j.snapshot()[0]['attempts'],1)
  with self.assertRaises(ValueError):self.j.finish(self.url,'confirmed','Duplicate','Duplicate')
 def test_skipped_role_cannot_be_submitted(self):
  self.j.review(self.job,self.digest,False,'Mandatory AIX experience not supported')
  self.assertFalse(self.j.claim(self.url,self.digest))
 def test_post_submit_interruption_can_be_reconciled_without_reapplying(self):
  self.j.review(self.job,self.digest,True,'Reviewed role');self.j.claim(self.url,self.digest)
  self.j.finish(self.url,'uncertain','Tracker interrupted after click')
  with self.assertRaises(ValueError):self.j.reconcile_confirmation(self.url,self.digest,'')
  self.j.reconcile_confirmation(self.url,self.digest,'Success message and Already Applied verified after reload')
  row=self.j.snapshot()[0];self.assertEqual(row['status'],'confirmed');self.assertEqual(row['attempts'],1)
  self.assertFalse(self.j.claim(self.url,self.digest))
 def test_confirmed_totals_survive_more_than_a_page_of_skipped_reviews(self):
  self.j.review(self.job,self.digest,True,'Reviewed role');self.j.claim(self.url,self.digest)
  self.j.finish(self.url,'confirmed','Confirmed by platform','Success and persisted platform record')
  with self.j.connect() as db:
   db.executemany('INSERT INTO applications (url,source,job,cv_sha256,status,reason,updated) VALUES (?,?,?,?,?,?,?)',[(self.url+str(i),'naukrigulf','{}',self.digest,'skipped','Unmatched role',9999999999+i) for i in range(510)])
  self.assertEqual(self.j.counts()['confirmed'],1);self.assertEqual(len(self.j.known_urls()),511)
  self.assertEqual(self.j.activity()[0]['status'],'confirmed')
