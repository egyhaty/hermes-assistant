"""Conservative per-worker AI token pacing; never rotates credentials or upgrades plans."""
import hashlib,os,threading,time
from collections import deque
class Budget:
 def __init__(self,limit=5000,window=61,clock=time.monotonic,sleep=time.sleep):
  self.limit=limit;self.window=window;self.clock=clock;self.sleep=sleep;self.events=deque();self.lock=threading.Lock();self.cache={}
 def invoke(self,runnable,prompt):
  key=hashlib.sha256((type(runnable).__name__+'\0'+str(prompt)).encode()).digest()
  with self.lock:
   if key in self.cache:return self.cache[key]
   # Two characters/token is deliberately conservative for English form prompts.
   cost=(len(str(prompt))+1)//2+1024
   if cost>self.limit:raise ValueError('AI prompt exceeds worker budget; required answer remains blank.')
   for attempt in range(2):
    while True:
     now=self.clock()
     while self.events and now-self.events[0][0]>=self.window:self.events.popleft()
     if sum(x[1] for x in self.events)+cost<=self.limit:break
     delay=max(0.01,self.window-(now-self.events[0][0]))
     print('AI token budget: waiting %.1f seconds before next request.'%delay,flush=True);self.sleep(delay)
    self.events.append((self.clock(),cost))
    try:
     result=runnable.invoke(prompt);self.cache[key]=result;return result
    except Exception as error:
     if getattr(error,'status_code',None)!=429 or attempt:raise
     try:delay=float(error.response.headers.get('retry-after','61'))
     except (AttributeError,TypeError,ValueError):delay=61
     if delay>65:raise
     delay=max(1,delay)+1
     print('AI provider rate limit: waiting %.1f seconds; one retry only.'%delay,flush=True);self.sleep(delay)
BUDGET=Budget()
def paced_invoke(runnable,prompt):
 return BUDGET.invoke(runnable,prompt) if os.environ.get('JOB_AI_PROVIDER')=='groq' else runnable.invoke(prompt)
