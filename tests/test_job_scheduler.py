import importlib.util,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'job-worker'/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class SchedulerTests(unittest.TestCase):
 def test_holds_job_and_never_starts_second_process(self):
  m=load('scheduler')
  responses=[{'running':True,'pid':123},{'running':True,'pid':123},{'running':False,'exit_code':0,'stop_reason':'Run finished'}]
  with patch.object(sys,'argv',['scheduler']),patch.object(m,'request',side_effect=responses) as req,patch.object(m.time,'sleep'):
   self.assertEqual(m.main(),0);self.assertEqual([x.args[0] for x in req.call_args_list],['/control/scheduled-start','/control/status','/control/status'])
 def test_existing_run_is_skipped_without_polling_or_restart(self):
  m=load('scheduler')
  with patch.object(sys,'argv',['scheduler']),patch.object(m,'request',return_value={'running':True,'skipped':True}) as req:
   self.assertEqual(m.main(),0);self.assertEqual(req.call_count,1)
 def test_check_does_not_start_applications(self):
  m=load('scheduler')
  with patch.object(sys,'argv',['scheduler','--check']),patch.object(m,'request',return_value={'ready':True,'started':False}) as req:
   self.assertEqual(m.main(),0);self.assertEqual(req.call_args.args[0],'/control/schedule-check')
 def test_cron_is_staged_isolated_and_forbids_overlap(self):
  objects=load('render').render('ghcr.io/example/jobs@sha256:'+'a'*64)['items'];cron=next(x for x in objects if x['kind']=='CronJob');spec=cron['spec']
  self.assertEqual(spec['schedule'],'0 */6 * * *');self.assertEqual(spec['timeZone'],'Africa/Cairo');self.assertEqual(spec['concurrencyPolicy'],'Forbid');self.assertTrue(spec['suspend'])
  job=spec['jobTemplate']['spec'];self.assertNotIn('activeDeadlineSeconds',job);pod=job['template']['spec'];self.assertFalse(pod['automountServiceAccountToken']);self.assertNotIn('volumes',pod)
  serialized=str(pod);self.assertNotIn('hermes-ssh',serialized);self.assertNotIn('hermes-jobs-auth',serialized);self.assertNotIn('hermes-free-api',serialized)
