import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('ai_budget',Path(__file__).resolve().parents[1]/'job-worker/ai_budget.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class Clock:
 def __init__(self):self.now=0;self.waits=[]
 def clock(self):return self.now
 def sleep(self,s):self.waits.append(s);self.now+=s
class Model:
 def __init__(self,errors=0):self.calls=0;self.errors=errors
 def invoke(self,prompt):
  self.calls+=1
  if self.calls<=self.errors:
   e=RuntimeError('quota');e.status_code=429;e.response=type('Response',(),{'headers':{'retry-after':'2'}})();raise e
  return 'fixture answer'
class BudgetTests(unittest.TestCase):
 def make(self,limit=2100):
  clock=Clock();return mod.Budget(limit=limit,clock=clock.clock,sleep=clock.sleep),clock
 def test_token_window_delays_distinct_calls(self):
  b,c=self.make();m=Model();b.invoke(m,'one');b.invoke(m,'two');b.invoke(m,'three');self.assertEqual(m.calls,3);self.assertEqual(c.waits,[61])
 def test_identical_prompt_reuses_private_memory_cache(self):
  b,c=self.make();m=Model();self.assertEqual(b.invoke(m,'same'),b.invoke(m,'same'));self.assertEqual(m.calls,1)
 def test_rate_limit_waits_then_one_retry_only(self):
  b,c=self.make(5000);m=Model(errors=5)
  with self.assertRaises(RuntimeError):b.invoke(m,'question')
  self.assertEqual(m.calls,2);self.assertEqual(c.waits,[3])
 def test_oversized_prompt_is_never_sent(self):
  b,c=self.make();m=Model()
  with self.assertRaises(ValueError):b.invoke(m,'x'*5000)
  self.assertEqual(m.calls,0)
