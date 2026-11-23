import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'job-worker'))
from application_policy import stretch_review,POLICY
from application_journal import Journal
class PolicyTests(unittest.TestCase):
 def decision(self):return dict(eligible=False,reason='Production AWS tenure and technical degree unverified',required_unknown=['Five years production AWS'],gaps=['Social Work degree'])
 def test_stretch_preserves_gaps_without_asserting_tenure(self):
  d=self.decision();out=stretch_review({'title':'Senior DevOps Engineer','description':'Linux Kubernetes AWS'},d)
  self.assertTrue(out['eligible']);self.assertIn('Five years production AWS',out['gaps']);self.assertEqual(d,self.decision());self.assertEqual(out['required_unknown'],[])
 def test_restrictions_and_wrong_roles_not_relaxed(self):
  for job in [{'title':'DevOps Engineer - UAE Nationals'},{'title':'Civil Infrastructure Engineer'},{'title':'Senior AI Systems Engineer'},{'title':'DevOps Engineer','description':'must reside in Pakistan'}]:self.assertFalse(stretch_review(job,self.decision())['eligible'])
  d=self.decision();d['reason']='UAE work authorization unknown';self.assertFalse(stretch_review({'title':'DevOps Engineer'},d)['eligible'])
 def test_remote_scope_not_changed(self):self.assertFalse(stretch_review({'title':'Linux Engineer'},self.decision(),'hosting_remote')['eligible'])
 def test_only_unattempted_old_skips_reconsidered_once(self):
  with tempfile.TemporaryDirectory() as tmp:
   j=Journal(Path(tmp)/'test.db');url='https://www.linkedin.com/jobs/view/12345/';digest='a'*64
   job={'source':'linkedin','url':url,'title':'DevOps Engineer','screening':dict(self.decision(),provider='codex')}
   j.review(job,digest,False,'Skills gap')
   self.assertIn(url,j.known_urls('codex',digest))
   self.assertNotIn(url,j.known_urls('codex',digest,POLICY))
   job['screening']=dict(stretch_review(job,self.decision()),provider='codex')
   self.assertEqual(j.review(job,digest,True,'Stretch'),'eligible');self.assertTrue(j.claim(url,digest))
   j.finish(url,'uncertain','Platform response unclear')
   self.assertIn(url,j.known_urls('codex',digest,POLICY));self.assertEqual(j.review(job,digest,True,'Retry'),'uncertain')
