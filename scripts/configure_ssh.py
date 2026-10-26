from pathlib import Path
import json,base64,subprocess
root=Path.home()/'.ssh';data={};identities=[]
for p in sorted(root.rglob('*')):
 if not p.is_file() or p.is_symlink():continue
 with p.open('rb') as f:header=f.read(128)
 if b'PRIVATE KEY-----' not in header:continue
 name=str(p.relative_to(root)).replace('/','__')
 if name in data:raise SystemExit('Duplicate flattened SSH key name; nothing changed')
 data[name]=base64.b64encode(p.read_bytes()).decode();identities.append(name)
if not identities:raise SystemExit('No private keys found; nothing changed')
for name in ('known_hosts','known_hosts2'):
 p=root/name
 if p.is_file() and not p.is_symlink():data[name]=base64.b64encode(p.read_bytes()).decode()
config=['Host *','    BatchMode yes','    IdentitiesOnly yes','    ForwardAgent no','    StrictHostKeyChecking yes','    UserKnownHostsFile /etc/hermes-ssh/known_hosts /etc/hermes-ssh/known_hosts2','    ConnectTimeout 10','    ConnectionAttempts 1']
config+=['    IdentityFile none']
data['config']=base64.b64encode(('\n'.join(config)+'\n').encode()).decode()
obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':'hermes-ssh','namespace':'hermes'},'type':'Opaque','data':data}
r=subprocess.run(['kubectl','--context','kubernetes-admin@kubernetes','--request-timeout=20s','apply','--server-side','--field-manager=hermes-owner','-f','-'],input=json.dumps(obj),text=True,capture_output=True,timeout=30)
if r.returncode:raise SystemExit('SSH Secret transfer failed; secret details withheld')
print('Secret/hermes-ssh applied; private key count:',len(identities))
print('Mounted identity filenames:',', '.join(identities))
