"""Render a stopped worker; activation requires reviewed node profiles and image scan."""
import argparse,json
from pathlib import Path

def render(image):
 if '@sha256:' not in image:raise ValueError('Immutable scanned image required')
 ns='hermes';name='hermes-jobs';labels={'app.kubernetes.io/name':name};meta=lambda n:{'name':n,'namespace':ns}
 pod={'hostname':'hermes-jobs','nodeSelector':{'kubernetes.io/hostname':'devops'},'automountServiceAccountToken':False,'terminationGracePeriodSeconds':30,
 'imagePullSecrets':[{'name':'hermes-registry'}],
 'securityContext':{'runAsNonRoot':True,'runAsUser':10000,'runAsGroup':10000,'fsGroup':10000,'fsGroupChangePolicy':'OnRootMismatch','seccompProfile':{'type':'Localhost','localhostProfile':'hermes-jobs-browser.json'}},
 'containers':[{'name':'jobs','image':image,'envFrom':[{'secretRef':{'name':'hermes-jobs-auth'}},{'secretRef':{'name':'hermes-free-api'}}],
 'securityContext':{'readOnlyRootFilesystem':True,'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']},'appArmorProfile':{'type':'Localhost','localhostProfile':'hermes-jobs-browser'}},
 'ports':[{'name':'http','containerPort':9118}],
 'resources':{'requests':{'cpu':'250m','memory':'512Mi'},'limits':{'cpu':'1','memory':'2Gi'}},
 'readinessProbe':{'httpGet':{'path':'/health','port':9118},'initialDelaySeconds':15,'periodSeconds':10},
 'volumeMounts':[{'name':'data','mountPath':'/data','subPath':'hermes-home/job-worker-data'},{'name':'tmp','mountPath':'/tmp'},{'name':'shm','mountPath':'/dev/shm'},{'name':'profile','mountPath':'/etc/job-profile','readOnly':True}]}],
 'volumes':[{'name':'profile','secret':{'secretName':'hermes-jobs-profile','optional':True,'defaultMode':288}},{'name':'data','persistentVolumeClaim':{'claimName':'hermes-data'}},{'name':'tmp','emptyDir':{'sizeLimit':'512Mi'}},{'name':'shm','emptyDir':{'medium':'Memory','sizeLimit':'256Mi'}}]}
 objects=[{'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{**meta('hermes-jobs-data'),'annotations':{'argocd.argoproj.io/sync-options':'Prune=false,Delete=false'}},'spec':{'accessModes':['ReadWriteOnce'],'storageClassName':'longhorn','resources':{'requests':{'storage':'5Gi'}}}},
 {'apiVersion':'apps/v1','kind':'Deployment','metadata':meta(name),'spec':{'replicas':0,'strategy':{'type':'Recreate'},'selector':{'matchLabels':labels},'template':{'metadata':{'labels':labels},'spec':pod}}},
 {'apiVersion':'v1','kind':'Service','metadata':meta(name),'spec':{'selector':labels,'ports':[{'name':'http','port':80,'targetPort':9118}]}},
 {'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':meta(name),'spec':{'podSelector':{'matchLabels':labels},'policyTypes':['Ingress','Egress'],
 'ingress':[{'from':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':'traefik'}},'podSelector':{'matchLabels':{'app.kubernetes.io/name':'traefik'}}},{'podSelector':{'matchLabels':{'app.kubernetes.io/name':'hermes-karem'}}}],'ports':[{'protocol':'TCP','port':9118}]}],
 'egress':[{'to':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':'kube-system'}},'podSelector':{'matchLabels':{'k8s-app':'kube-dns'}}}],'ports':[{'protocol':'UDP','port':53},{'protocol':'TCP','port':53}]},{'to':[{'ipBlock':{'cidr':'0.0.0.0/0','except':['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','169.254.0.0/16','127.0.0.0/8','66.11.126.176/28','224.0.0.0/4']}}],'ports':[{'protocol':'TCP','port':443}]}]}},
 {'apiVersion':'networking.k8s.io/v1','kind':'Ingress','metadata':{**meta(name),'annotations':{'traefik.ingress.kubernetes.io/router.entrypoints':'websecure','traefik.ingress.kubernetes.io/router.middlewares':'hermes-hermes-jobs-security@kubernetescrd,hermes-hermes-dashboard-rate-limit@kubernetescrd'}},'spec':{'ingressClassName':'traefik','tls':[{'hosts':['hermes.murabba.net'],'secretName':'hermes-dashboard-tls'}],'rules':[{'host':'hermes.murabba.net','http':{'paths':[{'path':'/jobs/','pathType':'Prefix','backend':{'service':{'name':name,'port':{'name':'http'}}}}]}}]}}]
 objects.append({'apiVersion':'traefik.io/v1alpha1','kind':'Middleware','metadata':meta('hermes-jobs-security'),'spec':{'headers':{'contentTypeNosniff':True,'referrerPolicy':'same-origin','stsSeconds':15552000}}})
 return {'apiVersion':'v1','kind':'List','items':[x for x in objects if x['kind']!='PersistentVolumeClaim']}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--image',required=True);p.add_argument('--out',required=True,type=Path);a=p.parse_args();a.out.parent.mkdir(exist_ok=True,parents=True);a.out.write_text(json.dumps(render(a.image),indent=2)+'\n')
