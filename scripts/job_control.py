"""Gateway client for the fixed job worker; credentials never enter argv or output."""
import argparse,json,os,urllib.request,urllib.error
from pathlib import Path
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['status','start','stop']);a=p.parse_args()
 token=Path('/etc/hermes-jobs/CONTROL_TOKEN').read_text().strip()
 req=urllib.request.Request('http://hermes-jobs.hermes.svc.cluster.local/control/'+a.action,headers={'Authorization':'Bearer '+token},method='GET' if a.action=='status' else 'POST')
 try:
  with urllib.request.urlopen(req,timeout=15) as r:result=json.load(r)
 except urllib.error.HTTPError as e:
  try:result=json.loads(e.read())
  except Exception:result={'error':'Worker request denied','status':e.code}
 except Exception:raise SystemExit('Job worker unavailable; no application status confirmed.') from None
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
