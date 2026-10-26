#!/usr/bin/env python3
"""Read a small fixed set of Prometheus queries; never modifies the cluster."""
import argparse,json,urllib.error,urllib.parse,urllib.request
BASE='http://monitoring-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090'
QUERIES={
 'nodes_ready':'kube_node_status_condition{condition="Ready",status="true"}',
 'deployments_available':'kube_deployment_status_replicas_available',
 'deployments_desired':'kube_deployment_spec_replicas',
 'targets_down':'up == 0',
 'container_restarts_last_hour':'sum(increase(kube_pod_container_status_restarts_total[1h]))',
}
def read_json(path):
 try:
  with urllib.request.urlopen(BASE+path,timeout=10) as response: result=json.load(response)
 except Exception: raise SystemExit('Monitoring unavailable; no cluster changes made.') from None
 if result.get('status')!='success': raise SystemExit('Prometheus query failed; details withheld.')
 return result['data']
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('view',choices=['summary','alerts'],nargs='?',default='summary');a=p.parse_args()
 if a.view=='summary':
  raw={k:read_json('/api/v1/query?'+urllib.parse.urlencode({'query':q}))['result'] for k,q in QUERIES.items()}
  def value(row): return float(row['value'][1])
  def deployments(rows): return {(x['metric'].get('namespace'),x['metric'].get('deployment')):value(x) for x in rows}
  available=deployments(raw['deployments_available']);desired=deployments(raw['deployments_desired'])
  result={'nodes':{'total':len(raw['nodes_ready']),'not_ready':[x['metric'].get('node') for x in raw['nodes_ready'] if value(x)!=1]},
   'deployments':{'total':len(desired),'unavailable':[{'namespace':ns,'name':name,'desired':count,'available':available.get((ns,name),0)} for (ns,name),count in desired.items() if available.get((ns,name),0)<count]},
   'targets_down':[{'job':x['metric'].get('job'),'instance':x['metric'].get('instance')} for x in raw['targets_down']],
   'container_restarts_last_hour':sum(value(x) for x in raw['container_restarts_last_hour'])}
 else:
  alerts=read_json('/api/v1/alerts')['alerts']
  result={'alerts':[{'state':x.get('state'),'activeAt':x.get('activeAt'),'labels':{k:v for k,v in x.get('labels',{}).items() if k in ('alertname','severity','namespace','node')}} for x in alerts]}
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
