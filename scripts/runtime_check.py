#!/usr/bin/env python3
"""Render an uncredentialed, restricted Kubernetes runtime inspection pod."""
import argparse
import json
from pathlib import Path
import re

def manifest(image):
    if not re.fullmatch(r'[A-Za-z0-9./_:-]+@sha256:[0-9a-f]{64}', image):
        raise ValueError('an immutable image digest is required')
    return {'apiVersion':'v1','kind':'Pod','metadata':{'name':'hermes-runtime-check','namespace':'hermes','labels':{'app.kubernetes.io/name':'hermes-runtime-check'}},'spec':{
        'restartPolicy':'Never','activeDeadlineSeconds':1800,'automountServiceAccountToken':False,
        'securityContext':{'runAsNonRoot':True,'runAsUser':10000,'runAsGroup':10000,'fsGroup':10000,'seccompProfile':{'type':'RuntimeDefault'}},
        'containers':[{'name':'check','image':image,'workingDir':'/opt/hermes',
            'command':['/opt/hermes/.venv/bin/python','-c','import time; print("Runtime inspection only; no gateway or model started", flush=True); time.sleep(1750)'],
            'env':[{'name':'HOME','value':'/opt/data'},{'name':'HERMES_HOME','value':'/opt/data'},{'name':'PYTHONDONTWRITEBYTECODE','value':'1'}],
            'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}},
            'resources':{'requests':{'cpu':'100m','memory':'512Mi'},'limits':{'cpu':'2','memory':'4Gi'}},
            'volumeMounts':[{'name':'data','mountPath':'/opt/data','subPath':'hermes-home'},{'name':'tmp','mountPath':'/tmp'}]}],
        'volumes':[{'name':'data','persistentVolumeClaim':{'claimName':'hermes-data'}},{'name':'tmp','emptyDir':{'sizeLimit':'1Gi'}}]}}

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    args=parser.parse_args()
    print(json.dumps(manifest(args.image),indent=2))
