#!/usr/bin/env python3
"""Verify Langfuse project keys privately and create a dedicated Secret."""
import argparse,base64,getpass,json,subprocess,urllib.request
HOSTS={'eu':'https://cloud.langfuse.com','us':'https://us.cloud.langfuse.com','jp':'https://jp.cloud.langfuse.com'}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--region',choices=HOSTS,default='eu');p.add_argument('--context',default='kubernetes-admin@kubernetes');a=p.parse_args()
 public=getpass.getpass('Langfuse project PUBLIC key (hidden): ').strip();secret=getpass.getpass('Langfuse project SECRET key (hidden): ').strip()
 if not public.startswith('pk-lf-') or not secret.startswith('sk-lf-') or any(c.isspace() for c in public+secret):raise SystemExit('Unexpected key format; nothing changed.')
 host=HOSTS[a.region];auth=base64.b64encode((public+':'+secret).encode()).decode()
 req=urllib.request.Request(host+'/api/public/projects',headers={'Authorization':'Basic '+auth})
 try:
  with urllib.request.build_opener(NoRedirect()).open(req,timeout=20) as r:data=json.load(r)
  if not isinstance(data.get('data'),list) or not data['data']:raise ValueError()
 except Exception:raise SystemExit('Langfuse verification failed; check keys/region. Credential details withheld.') from None
 values={'HERMES_LANGFUSE_PUBLIC_KEY':public,'HERMES_LANGFUSE_SECRET_KEY':secret,'HERMES_LANGFUSE_BASE_URL':host}
 obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':'hermes-langfuse','namespace':'hermes'},'type':'Opaque','stringData':values}
 r=subprocess.run(['kubectl','--context',a.context,'apply','--server-side','--field-manager=hermes-owner','-f','-'],input=json.dumps(obj),text=True,capture_output=True)
 if r.returncode:raise SystemExit('Secret creation failed; credential details withheld.')
 print(r.stdout.strip());print('Project credentials verified. No conversation or email content sent; tracing activation is separate.')
if __name__=='__main__':main()
