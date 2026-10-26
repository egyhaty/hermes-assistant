import importlib.util,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
class RunStatusTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  spec=importlib.util.spec_from_file_location('run_status',Path(__file__).resolve().parents[1]/'job-worker/run_status.py');self.m=importlib.util.module_from_spec(spec)
  with patch.dict(os.environ,{'JOB_RUN_STATE':self.tmp.name+'/state.json'}):spec.loader.exec_module(self.m)
 def test_exit_preserves_limit_reason(self):
  self.m.started();self.m.stopped('10 submission attempts reached');self.m.exited(0)
  self.assertEqual(self.m.read()['stop_reason'],'10 submission attempts reached');self.assertEqual(self.m.read()['exit_code'],0)
 def test_new_run_clears_prior_stop(self):
  self.m.stopped('Stopped by user');self.m.started();self.assertIsNone(self.m.read()['stop_reason'])
 def test_explicit_time_and_attempt_limits(self):
  with patch.dict(os.environ,{'JOB_RUN_SECONDS':'3600'}):
   self.assertFalse(self.m.limit_reached(0,0,0,1000));self.assertTrue(self.m.limit_reached(0,0,0,3601))
  self.assertEqual(self.m.read()['stop_reason'],'60 minute session limit reached')
  self.assertTrue(self.m.limit_reached(0,10,0,10));self.assertEqual(self.m.read()['stop_reason'],'10 submission attempts reached')
