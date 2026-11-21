import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'job-worker'))
from application_journal import Journal
from naukri_adapter import submit,inspect_job

class NaukriAdapterTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.j=Journal(Path(self.tmp.name)/'journal.db');self.digest='a'*64
  self.job={'source':'naukrigulf','url':'https://www.naukrigulf.com/linux-jobs-in-dubai-jid-123456','title':'Linux Administrator','head':'Dubai, UAE','easyApply':True}
  self.j.review(self.job,self.digest,True,'Reviewed Linux job in UAE')
 def page(self,result):
  owner=self
  class Page:
   clicks=0
   def js(self,code):
    if 'b.click()' in code:
     owner.assertEqual(owner.j.snapshot()[0]['status'],'attempting')
     self.clicks+=1;return True
    return result
  return Page()
 def test_existing_platform_application_never_clicks_apply(self):
  p=self.page({});job=dict(self.job,head='Already Applied')
  self.assertEqual(submit(p,job,self.j,self.digest),'already_applied');self.assertEqual(p.clicks,0)
 def test_multiline_heading_keeps_company_separate_from_job_title(self):
  job=dict(self.job,title='Linux Administrator\nExample Company',company='',description='Monitor Linux servers and backups.',challenge=False)
  class Page:
   def goto(self,url):pass
   def wait(self,*args):return True
   def js(self,code):return job
  result=inspect_job(Page(),self.job['url'])
  self.assertEqual(result['title'],'Linux Administrator');self.assertEqual(result['company'],'Example Company')
 def test_unknown_required_form_gets_no_additional_submit(self):
  p=self.page({'head':'Complete application','fields':[{'name':'work_permit','required':True}],'buttons':['Submit']})
  self.assertEqual(submit(p,self.job,self.j,self.digest),'needs_input');self.assertEqual(p.clicks,1)
  self.assertEqual(self.j.snapshot()[0]['status'],'needs_input')
 def test_success_text_alone_does_not_count_without_persisted_platform_state(self):
  p=self.page({'head':'You have successfully applied to Linux Administrator','fields':[],'buttons':[]})
  with patch('naukri_adapter.inspect_job',return_value={'head':'Apply now'}):
   self.assertEqual(submit(p,self.job,self.j,self.digest),'uncertain')
  self.assertFalse(self.j.claim(self.job['url'],self.digest));self.assertEqual(p.clicks,1)
 def test_persisted_platform_confirmation_counts_exactly_one_attempt(self):
  p=self.page({'head':'You have successfully applied to Linux Administrator','fields':[],'buttons':[]})
  with patch('naukri_adapter.inspect_job',return_value={'head':'Linux Administrator Already Applied'}) as inspect:
   self.assertEqual(submit(p,self.job,self.j,self.digest),'confirmed')
   inspect.assert_called_once_with(p,self.job['url'])
  self.assertEqual(self.j.snapshot()[0]['attempts'],1)
  self.assertEqual(submit(p,self.job,self.j,self.digest),'not_claimed');self.assertEqual(p.clicks,1)
