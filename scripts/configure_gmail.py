#!/usr/bin/env python3
"""Store a Gmail app password directly in the dedicated Kubernetes Secret."""
import argparse,getpass,json,re,subprocess

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--context',default='kubernetes-admin@kubernetes')
    a=p.parse_args()
    password=''.join(getpass.getpass('Gmail APP password (16 characters; hidden): ').split())
    if not re.fullmatch(r'[A-Za-z0-9]{16}',password):
        raise SystemExit('Expected a 16-character Google app password; nothing changed. Do not use your Google account password.')
    obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':'hermes-gmail','namespace':'hermes'},'type':'Opaque','stringData':{'HIMALAYA_APP_PASS':password}}
    r=subprocess.run(['kubectl','--context',a.context,'apply','--server-side','--field-manager=hermes-owner','-f','-'],input=json.dumps(obj),text=True,capture_output=True)
    if r.returncode: raise SystemExit('Secret creation failed; credential details withheld.')
    print(r.stdout.strip())
    print('App password saved. The projected Secret updates automatically; no email was read or sent.')

if __name__=='__main__': main()
