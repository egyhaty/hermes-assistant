#!/usr/bin/env python3
"""Apply exact, audited patch versions to installed Node packages during image build.
No lifecycle scripts run. Existing consumers retain their package locations.
"""
import hashlib,base64,io,json,shutil,tarfile,tempfile,urllib.request
from pathlib import Path
pins=json.loads(Path('/opt/karem-build/security-pins.json').read_text())['node']
root=Path('/opt/hermes')
# Only package directories are replaced; project lockfiles remain upstream reference evidence.
locations={name:[] for name in pins}
for file in root.rglob('package.json'):
    if 'node_modules' not in file.parts:continue
    try:p=json.loads(file.read_text())
    except (ValueError,OSError):continue
    if p.get('name') in pins and p.get('version')!=pins[p['name']]:locations[p['name']].append(file.parent)
for name,paths in locations.items():
    if not paths:continue
    version=pins[name]
    with urllib.request.urlopen('https://registry.npmjs.org/'+name+'/'+version,timeout=30) as response:meta=json.load(response)
    dist=meta['dist']
    with urllib.request.urlopen(dist['tarball'],timeout=60) as response:raw=response.read()
    algo,expected=dist['integrity'].split('-',1)
    if algo!='sha512' or base64.b64encode(hashlib.sha512(raw).digest()).decode()!=expected:raise RuntimeError('npm integrity mismatch: '+name)
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:archive.extractall(tmp,filter='data')
        source=Path(tmp)/'package'
        for path in sorted(paths,key=lambda p:len(p.parts),reverse=True):
            # Preserve preexisting nested dependency resolution for these compatible patch updates.
            nested=path/'node_modules'
            saved=None
            if nested.exists():saved=Path(tmp)/('nested-'+str(len(str(path))));shutil.move(str(nested),saved)
            shutil.rmtree(path)
            shutil.copytree(source,path)
            if saved is not None:shutil.move(str(saved),path/'node_modules')
    print('Patched',name,version,'locations',len(paths))
