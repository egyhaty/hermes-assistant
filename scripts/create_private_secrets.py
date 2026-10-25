#!/usr/bin/env python3
"""Create Hermes Secrets from private files without printing credential values.
Run manually in an owner terminal once the provider has been selected.
"""
import argparse,json,os,re,subprocess
from pathlib import Path

def apply_secret(context,name,data):
    obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':name,'namespace':'hermes'},'type':'Opaque','stringData':data}
    subprocess.run(['kubectl','--context',context,'apply','--server-side','--field-manager=hermes-owner','-f','-'],input=json.dumps(obj),text=True,check=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--context',default='kubernetes-admin@kubernetes')
    p.add_argument('--credentials',type=Path,required=True,help='Private JSON file; never put it in git')
    p.add_argument('--profile',type=Path,required=True)
    a=p.parse_args()
    for path in (a.credentials,a.profile):
        if path.is_symlink() or path.stat().st_mode & 0o077:
            p.error('Private input files must be regular files with mode 0600')
    credentials=json.loads(a.credentials.read_text())
    if not isinstance(credentials,dict) or not all(isinstance(k,str) and re.fullmatch('[A-Z][A-Z0-9_]*',k) and isinstance(v,str) and v for k,v in credentials.items()):
        p.error('Credentials must be a JSON object of nonempty environment strings')
    users=credentials.get('TELEGRAM_ALLOWED_USERS','')
    if not users or not all(u.strip().isdigit() and int(u.strip())>0 for u in users.split(',')) or not credentials.get('TELEGRAM_BOT_TOKEN'):
        p.error('Telegram bot token and positive numeric owner allowlist are required')
    profile=json.loads(a.profile.read_text())
    if not all(isinstance(profile.get(k),str) and profile[k] for k in ['name','arabic_name','language','communication']):
        p.error('Profile is incomplete')
    # Values go only to kubectl stdin/API; never to arguments, stdout, git or a temporary file.
    apply_secret(a.context,'hermes-profile',{'profile.json':json.dumps(profile,ensure_ascii=False)})
    apply_secret(a.context,'hermes-credentials',credentials)
