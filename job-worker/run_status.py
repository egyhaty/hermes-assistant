"""Operational run metadata only; never stores applicant data or web sessions."""
import json,os,time
from pathlib import Path
STATE=Path(os.environ.get('JOB_RUN_STATE','/data/.last-run-state.json'))
def read():
 try:return json.loads(STATE.read_text())
 except (OSError,ValueError):return {}
def write(data):
 tmp=STATE.with_suffix('.tmp');fd=os.open(tmp,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
 with os.fdopen(fd,'w') as f:json.dump(data,f)
 tmp.chmod(0o600);tmp.replace(STATE)
def started():write({'started_at':time.time(),'stop_reason':None,'exit_code':None})
def stopped(reason):
 data=read();data.update(stop_reason=reason,ended_at=time.time());write(data)
def exited(code):
 data=read();data.update(exit_code=code,ended_at=time.time())
 if not data.get('stop_reason'):data['stop_reason']='Run finished' if code==0 else 'Process exited with code '+str(code)
 write(data)
def limit_reached(confirmed,attempted,inspected,elapsed):
 try:seconds=max(900,min(3600,int(os.environ.get('JOB_RUN_SECONDS','900'))))
 except ValueError:seconds=900
 reason=('10 submission attempts reached' if attempted>=10 else '10 confirmed applications reached' if confirmed>=10 else '60 inspected jobs reached' if inspected>=60 else str(seconds//60)+' minute session limit reached' if elapsed>seconds else None)
 if reason:stopped(reason);print('Run stopped: '+reason,flush=True)
 return bool(reason)
