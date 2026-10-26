"""Kubernetes CronJob client. Holds the Job until the one tracked run ends."""
import argparse,json,os,sys,time,urllib.request,urllib.error
BASE='http://hermes-jobs.hermes.svc.cluster.local'
def request(path,method='GET',timeout=20):
 req=urllib.request.Request(BASE+path,method=method,headers={'Authorization':'Bearer '+os.environ['CONTROL_TOKEN']})
 try:
  with urllib.request.urlopen(req,timeout=timeout) as response:return json.load(response)
 except urllib.error.HTTPError as error:
  try:message=json.load(error).get('error','HTTP '+str(error.code))
  except Exception:message='HTTP '+str(error.code)
  raise RuntimeError(message) from None

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
 result=request('/control/schedule-check' if args.check else '/control/scheduled-start','POST',timeout=120)
 if args.check:
  print(json.dumps(result));return 0 if result.get('ready') or result.get('skipped') else 1
 if result.get('skipped'):
  print('Skipped: an existing application run is active.');return 0
 if not result.get('running') or not result.get('pid'):raise RuntimeError('Worker did not acknowledge a started run.')
 pid=result['pid'];print('Scheduled application cycle started; holding Job until completion.',flush=True)
 failures=0
 while True:
  time.sleep(30)
  try:status=request('/control/status');failures=0
  except Exception:
   failures+=1
   if failures>=10:raise RuntimeError('Lost worker status; no second run was started.') from None
   continue
  if not status.get('running'):
   print('Cycle ended: '+str(status.get('stop_reason') or 'worker stopped'),flush=True)
   return 0 if status.get('exit_code') in (None,0) else 1
  if status.get('pid')!=pid:raise RuntimeError('Run tracking changed; refusing to follow a different run.')
if __name__=='__main__':
 try:sys.exit(main())
 except Exception as error:print('Scheduled cycle not completed: '+str(error),file=sys.stderr,flush=True);sys.exit(1)
