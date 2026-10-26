#!/usr/bin/env python3
"""Mirror only the job control capability to the gateway's dedicated Secret."""
import json,subprocess
CMD=['kubectl','--context','kubernetes-admin@kubernetes','--request-timeout=20s']
def main():
 r=subprocess.run(CMD+['-n','hermes','get','secret','hermes-jobs-auth','-o','json'],capture_output=True,text=True,timeout=30)
 if r.returncode:raise SystemExit('Worker control credential unavailable; nothing changed.')
 token=json.loads(r.stdout)['data']['CONTROL_TOKEN']
 obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':'hermes-jobs-control','namespace':'hermes'},'type':'Opaque','data':{'CONTROL_TOKEN':token}}
 r=subprocess.run(CMD+['apply','--server-side','--field-manager=hermes-owner','-f','-'],input=json.dumps(obj),capture_output=True,text=True,timeout=30)
 if r.returncode:raise SystemExit('Control Secret write failed; credential details withheld.')
 print('Secret/hermes-jobs-control saved; only start/status/stop capability shared with gateway.')
if __name__=='__main__':main()
