#!/usr/bin/env python3
"""Create a namespace-only GHCR image pull Secret from a dedicated read:packages token."""
import base64,getpass,json,subprocess
username=input('GitHub username [egyhaty]: ').strip() or 'egyhaty'
token=getpass.getpass('Dedicated GitHub read:packages token (not printed): ')
if not token:raise SystemExit('No token supplied; nothing changed')
config={'auths':{'ghcr.io':{'username':username,'password':token,'auth':base64.b64encode((username+':'+token).encode()).decode()}}}
obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':'hermes-registry','namespace':'hermes'},'type':'kubernetes.io/dockerconfigjson','stringData':{'.dockerconfigjson':json.dumps(config)}}
subprocess.run(['kubectl','--context','kubernetes-admin@kubernetes','apply','--server-side','--field-manager=hermes-owner','-f','-'],input=json.dumps(obj),text=True,check=True)
