#!/usr/bin/env python3
"""Share only the owner-authorized Groq credential with the Hermes gateway."""
import json,subprocess
CMD=['kubectl','--context','kubernetes-admin@kubernetes','--request-timeout=20s']
def main():
 r=subprocess.run(CMD+['-n','hermes','get','secret','hermes-jobs-groq','-o','json'],capture_output=True,text=True,timeout=30)
 if r.returncode:raise SystemExit('Groq source Secret unavailable; nothing changed.')
 key=json.loads(r.stdout).get('data',{}).get('GROQ_API_KEY')
 if not key:raise SystemExit('Groq key missing; nothing changed.')
 obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':'hermes-groq','namespace':'hermes'},'type':'Opaque','data':{'GROQ_API_KEY':key}}
 r=subprocess.run(CMD+['apply','--server-side','--field-manager=hermes-owner','-f','-'],input=json.dumps(obj),capture_output=True,text=True,timeout=30)
 if r.returncode:raise SystemExit('Groq Secret write failed; credential details withheld.')
 print('Secret/hermes-groq saved; only GROQ_API_KEY shared with the gateway.')
if __name__=='__main__':main()
