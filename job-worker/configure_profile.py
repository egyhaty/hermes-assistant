"""Import owner CV and verified application facts privately into Kubernetes."""
import argparse,base64,json,subprocess
from pathlib import Path
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cv',required=True,type=Path);p.add_argument('--facts',required=True,type=Path);a=p.parse_args()
 cv=a.cv.read_bytes();facts=json.loads(a.facts.read_text())
 if not cv.startswith(b'%PDF-') or len(cv)>600000:raise SystemExit('Use a PDF resume smaller than 600 KB for private Secret import.')
 if not isinstance(facts,dict):raise SystemExit('Facts must be a JSON object.')
 obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':'hermes-jobs-profile','namespace':'hermes'},'type':'Opaque','data':{'resume.pdf':base64.b64encode(cv).decode(),'profile.json':base64.b64encode(json.dumps(facts).encode()).decode()}}
 r=subprocess.run(['kubectl','--context','kubernetes-admin@kubernetes','--request-timeout=20s','apply','--server-side','--field-manager=hermes-owner','-f','-'],input=json.dumps(obj),capture_output=True,text=True,timeout=30)
 if r.returncode:raise SystemExit('Profile import failed; personal details withheld.')
 print('Secret/hermes-jobs-profile saved; no job application submitted.')
if __name__=='__main__':main()
