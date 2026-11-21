import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'job-worker'))
from job_matching import parse_decision,professional_facts,local_screen

class JobMatchingTests(unittest.TestCase):
 def test_unknown_mandatory_requirements_block_automatic_submission(self):
  d=parse_decision('{"eligible":true,"reason":"Uncertain","required_unknown":["Work permit"],"gaps":[]}')
  self.assertFalse(d['eligible'])
 def test_string_boolean_cannot_enable_a_submission(self):
  with self.assertRaises(ValueError):parse_decision('{"eligible":"true","reason":"test","required_unknown":[],"gaps":[]}')
 def test_incomplete_response_fails_closed(self):
  with self.assertRaises(ValueError):parse_decision('{"eligible":true,"reason":"test"}')
 def test_matching_profile_omits_contact_details_and_preserves_boundaries(self):
  c={'questions':{'user_information_all':'Professional Summary\nLinux ops. user@example.test +971 50 123 4567\nDevOps Project\nLab only\nTechnical Skills\nLinux\nProfessional Experience\nBoundary: AWS labs are not production years.'}}
  facts=professional_facts(c);self.assertNotIn('user@example.test',str(facts));self.assertNotIn('+971 50 123 4567',str(facts));self.assertIn('not production',facts['Limits'])
 def test_local_matching_rejects_unverified_specialised_platform(self):
  d=local_screen({'questions':{'user_information_all':'Professional Summary\nLinux operations\nDevOps Project'}}, {'title':'Linux Engineer','head':'Dubai, UAE','description':'Manage Linux servers, backups and networking. Administer AIX.'})
  self.assertFalse(d['eligible']);self.assertTrue(any('AIX' in x for x in d['required_unknown']))
 def test_local_matching_does_not_promote_labs_to_production_cloud(self):
  d=local_screen({'questions':{'user_information_all':'Professional Summary\nLinux operations\nDevOps Project'}}, {'title':'Cloud Engineer','head':'Dubai, UAE','description':'Manage Linux servers, backups and networking. Architect production AWS environments.'})
  self.assertFalse(d['eligible'])
 def test_local_matching_can_accept_basic_supervised_cloud_support(self):
  d=local_screen({'questions':{'user_information_all':'Professional Summary\nLinux operations\nDevOps Project'}}, {'title':'Systems Engineer','head':'Dubai, UAE','description':'Monitor Linux servers, maintain backups and troubleshoot incidents. Assist with basic Azure administration under supervision.'})
  self.assertTrue(d['eligible']);self.assertTrue(d['gaps'])
