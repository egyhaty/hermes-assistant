#!/usr/bin/env python3
"""Save a Groq free-plan key for the isolated Kubernetes jobs worker only."""
import argparse,getpass,json,subprocess,urllib.request,urllib.error
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--context',default='kubernetes-admin@kubernetes');args=parser.parse_args()
 print('Use a dedicated Groq Free Plan account/project without billing. The API does not verify your billing plan here.')
 if input('Confirm the Groq console shows Free Plan (type FREE): ').strip()!='FREE':raise SystemExit('Nothing changed.')
 key=getpass.getpass('Groq API key (hidden): ').strip()
 if not key.startswith('gsk_') or any(c.isspace() for c in key):raise SystemExit('No valid key supplied; nothing changed.')
 req=urllib.request.Request('https://api.groq.com/openai/v1/models',headers={'Authorization':'Bearer '+key,'User-Agent':'hermes-jobs-setup/1.0','Accept':'application/json'})
 try:
  with urllib.request.build_opener(NoRedirect()).open(req,timeout=25) as r:models=json.load(r)
  if 'openai/gpt-oss-120b' not in {x['id'] for x in models['data']}:raise ValueError()
 except urllib.error.HTTPError as e:raise SystemExit('Groq verification returned HTTP '+str(e.code)+'; nothing changed. Check key validity and project permissions. Credential details withheld.') from None
 except Exception:raise SystemExit('Key/model verification failed; nothing changed. Credential details withheld.') from None
 obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':'hermes-jobs-groq','namespace':'hermes'},'type':'Opaque','stringData':{'GROQ_API_KEY':key,'JOB_AI_PROVIDER':'groq'}}
 result=subprocess.run(['kubectl','--context',args.context,'--request-timeout=20s','apply','--server-side','--field-manager=hermes-owner','-f','-'],input=json.dumps(obj),capture_output=True,text=True,timeout=30)
 if result.returncode:raise SystemExit('Secret write failed; credential details withheld.')
 print('Secret/hermes-jobs-groq saved. No inference request made. Only the jobs worker will use it after rollout; Hermes main provider is unchanged.')
if __name__=='__main__':main()
