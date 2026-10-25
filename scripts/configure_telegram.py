#!/usr/bin/env python3
"""Collect Telegram credentials locally and send them directly to Kubernetes stdin."""
import argparse,getpass,json,re,subprocess,sys

def ask(prompt,hidden=False,dialog=False):
    if dialog:
        script='text returned of (display dialog '+json.dumps(prompt)+' default answer "" with title "Hermes Kubernetes setup"'+(' with hidden answer' if hidden else '')+')'
        return subprocess.check_output(['osascript','-e',script],text=True).strip()
    return getpass.getpass(prompt+': ') if hidden else input(prompt+': ').strip()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--macos-dialog',action='store_true')
    p.add_argument('--context',default='kubernetes-admin@kubernetes')
    a=p.parse_args()
    try:
        token=ask('Telegram bot token from BotFather (kept private)',True,a.macos_dialog)
        users=ask('Positive numeric Telegram owner user ID (or comma-separated IDs)',False,a.macos_dialog)
        if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+',token) or not users or not all(x.strip().isdigit() and int(x.strip())>0 for x in users.split(',')):
            sys.exit('Invalid Telegram token or owner IDs; no Secret created')
        obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':'hermes-credentials','namespace':'hermes'},'type':'Opaque','stringData':{'TELEGRAM_BOT_TOKEN':token,'TELEGRAM_ALLOWED_USERS':','.join(x.strip() for x in users.split(','))}}
        subprocess.run(['kubectl','--context',a.context,'apply','--server-side','--field-manager=hermes-owner','-f','-'],input=json.dumps(obj),text=True,check=True)
        print('Telegram Secret created. Gateway remains inactive pending acceptance.')
    except subprocess.CalledProcessError:
        sys.exit('Setup cancelled or Kubernetes command failed; credential values were not printed')
