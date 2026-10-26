import importlib.util,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def module(name):
 s=importlib.util.spec_from_file_location(name,ROOT/'job-worker'/f'{name}.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class JobWorkerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  with patch.dict(os.environ,{'JOB_DATA':self.tmp.name}):self.g=module('worker_guard')
  self.data=Path(self.tmp.name);(self.data/'resume.pdf').write_bytes(b'%PDF-1.7\nfixture')
  self.config={'personals':{'first_name':'Owner','last_name':'Fixture','phone_number':'123','current_city':'Cairo'},'questions':{'years_of_experience':'3','require_visa':'Yes','legally_authorized':'No','notice_period':30},'secrets':{'use_AI':False},'search':{'easy_apply_only':True}}
  self.save()
 def save(self):(self.data/'user_config.json').write_text(json.dumps(self.config))
 def test_missing_work_authorization_blocks_run(self):
  self.config['questions']['legally_authorized']='';self.save();self.assertIn('legally_authorized',self.g.require_ready())
 def test_paid_model_is_rejected(self):
  self.config['secrets']={'use_AI':True,'llm_model':'paid-model'};self.save();self.assertIn('free',self.g.validate())
 def test_profile_or_resume_change_invalidates_setup(self):
  (self.data/'profile-ready').write_text(self.g.profile_digest());(self.data/'resume.pdf').write_bytes(b'%PDF-1.7\nchanged')
  self.assertIn('Profile changed',self.g.require_ready())
 def test_external_apply_is_rejected(self):
  self.config['search']['easy_apply_only']=False;self.save();self.assertIn('Easy Apply',self.g.validate())
 def test_absent_signin_blocks_submission(self):
  (self.data/'profile-ready').write_text(self.g.profile_digest())
  with patch.object(self.g.urllib.request,'urlopen',side_effect=OSError()):self.assertIn('sign in',self.g.require_ready())
 def test_render_is_stopped_and_has_no_owner_ssh_or_admin_credentials(self):
  objects=module('render').render('ghcr.io/example/jobs@sha256:'+'a'*64)['items'];d=next(x for x in objects if x['kind']=='Deployment');self.assertEqual(d['spec']['replicas'],0)
  pod=d['spec']['template']['spec'];self.assertFalse(pod['automountServiceAccountToken']);self.assertNotIn('hostPath',json.dumps(pod));self.assertNotIn('hermes-ssh',json.dumps(pod));self.assertNotIn('hermes-profile',json.dumps(pod));self.assertEqual(pod['securityContext']['seccompProfile']['type'],'Localhost')
