"""Provision only a password verifier and a dedicated job-control token; no SSH keys."""
import base64,json,secrets,subprocess
CMD=['kubectl','--context','kubernetes-admin@kubernetes','--request-timeout=20s']
def main():
 r=subprocess.run(CMD+['-n','hermes','get','secret','hermes-dashboard-auth','-o','json'],capture_output=True,text=True,timeout=30)
 if r.returncode:raise SystemExit('Could not read existing UI password verifier; nothing changed.')
 d=json.loads(r.stdout)['data'];values={
 'USERNAME':base64.b64decode(d['HERMES_DASHBOARD_BASIC_AUTH_USERNAME']).decode(),
 'PASSWORD_HASH':base64.b64decode(d['HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH']).decode(),
 'CONTROL_TOKEN':secrets.token_urlsafe(32)}
 obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':'hermes-jobs-auth','namespace':'hermes'},'type':'Opaque','stringData':values}
 r=subprocess.run(CMD+['apply','--server-side','--field-manager=hermes-owner','-f','-'],input=json.dumps(obj),capture_output=True,text=True,timeout=30)
 if r.returncode:raise SystemExit('Job auth Secret write failed; details withheld.')
 print('Secret/hermes-jobs-auth saved. UI uses the existing username/password; no signing key or SSH keys copied.')
if __name__=='__main__':main()
