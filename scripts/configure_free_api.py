#!/usr/bin/env python3
"""Privately install a free OpenRouter key and optional dashboard login Secret."""
import argparse,base64,getpass,hashlib,json,secrets,subprocess,urllib.request

def apply(context,name,values):
    obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':name,'namespace':'hermes'},'type':'Opaque','stringData':values}
    r=subprocess.run(['kubectl','--context',context,'apply','--server-side','--field-manager=hermes-owner','-f','-'],input=json.dumps(obj),text=True,capture_output=True)
    if r.returncode: raise SystemExit('Secret write failed; credential details withheld.')
    print(r.stdout.strip())

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--context',default='kubernetes-admin@kubernetes');p.add_argument('--dashboard',action='store_true');a=p.parse_args()
    key=getpass.getpass('OpenRouter API key (hidden): ').strip()
    if not key.startswith('sk-or-') or any(c.isspace() for c in key): raise SystemExit('No valid key supplied; nothing changed.')
    req=urllib.request.Request('https://openrouter.ai/api/v1/key',headers={'Authorization':'Bearer '+key})
    try:
        with urllib.request.urlopen(req,timeout=25) as r: data=json.load(r)['data']
    except Exception: raise SystemExit('Key verification failed; nothing changed. Credential details withheld.') from None
    if data.get('is_free_tier') is not True: raise SystemExit('Key is not reported as free-tier; nothing changed. Use a dedicated free account/key.')
    dashboard=None
    if a.dashboard:
        pw=getpass.getpass('Choose dashboard password (12+ characters, hidden): ')
        if len(pw)<12 or pw!=getpass.getpass('Confirm dashboard password (hidden): '): raise SystemExit('Password too short or confirmation differs; nothing changed.')
        salt=secrets.token_bytes(16);dk=hashlib.scrypt(pw.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)
        encoded='scrypt$16384$8$1$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(dk).decode()
        dashboard={'HERMES_DASHBOARD_BASIC_AUTH_USERNAME':'karem','HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH':encoded,'HERMES_DASHBOARD_BASIC_AUTH_SECRET':base64.b64encode(secrets.token_bytes(32)).decode()}
    apply(a.context,'hermes-free-api',{'OPENROUTER_API_KEY':key})
    if dashboard: apply(a.context,'hermes-dashboard-auth',dashboard)
    print('Secrets saved; no provider change or model request made. Dashboard username: karem' if dashboard else 'API Secret saved; no provider change or model request made.')

if __name__=='__main__': main()
