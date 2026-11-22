"""Stopped self-hosted GPT matcher resources; no public ingress or browser credentials."""


def render(image):
    labels = {'app.kubernetes.io/name': 'hermes-jobs-gpt'}
    jobs = {'app.kubernetes.io/name': 'hermes-jobs'}
    meta = lambda name: {'name': name, 'namespace': 'hermes'}
    restricted = {'readOnlyRootFilesystem': True, 'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}}
    prepare = "from pathlib import Path; import os; p=Path('/parent/job-gpt'); assert not p.is_symlink(); p.mkdir(mode=0o700,exist_ok=True); assert p.stat().st_uid==os.getuid(); p.chmod(0o700)"
    pod = {'nodeSelector': {'kubernetes.io/hostname': 'devops'}, 'automountServiceAccountToken': False,
           'imagePullSecrets': [{'name': 'hermes-registry'}],
           'securityContext': {'runAsNonRoot': True, 'runAsUser': 10000, 'runAsGroup': 10000, 'fsGroup': 10000,
                               'fsGroupChangePolicy': 'OnRootMismatch', 'seccompProfile': {'type': 'RuntimeDefault'}},
           'initContainers': [{'name': 'prepare-gpt-home', 'image': image, 'command': ['python', '-c', prepare],
                               'securityContext': restricted, 'volumeMounts': [{'name': 'data', 'mountPath': '/parent', 'subPath': 'hermes-home'}]}],
           'containers': [{'name': 'gpt', 'image': image, 'command': ['python', '/opt/worker/gpt_matcher.py'],
                           'env': [{'name': 'GPT_AUTH_DIR', 'value': '/data/codex'},
                                   {'name': 'GPT_MATCHER_TOKEN', 'valueFrom': {'secretKeyRef': {'name': 'hermes-jobs-matcher-auth', 'key': 'GPT_MATCHER_TOKEN'}}}],
                           'ports': [{'name': 'http', 'containerPort': 9120}], 'securityContext': restricted,
                           'resources': {'requests': {'cpu': '100m', 'memory': '128Mi'}, 'limits': {'cpu': '1', 'memory': '768Mi'}},
                           'startupProbe': {'httpGet': {'path': '/health', 'port': 9120}, 'periodSeconds': 5, 'failureThreshold': 24},
                           'readinessProbe': {'httpGet': {'path': '/health', 'port': 9120}, 'periodSeconds': 10},
                           'livenessProbe': {'httpGet': {'path': '/health', 'port': 9120}, 'periodSeconds': 15},
                           'volumeMounts': [{'name': 'data', 'mountPath': '/data', 'subPath': 'hermes-home/job-gpt'},
                                            {'name': 'tmp', 'mountPath': '/tmp'}]}],
           'volumes': [{'name': 'data', 'persistentVolumeClaim': {'claimName': 'hermes-data'}},
                       {'name': 'tmp', 'emptyDir': {'sizeLimit': '256Mi'}}]}
    return {'apiVersion': 'v1', 'kind': 'List', 'items': [
        {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': meta('hermes-jobs-gpt'),
         'spec': {'replicas': 0, 'strategy': {'type': 'Recreate'}, 'selector': {'matchLabels': labels},
                  'template': {'metadata': {'labels': labels}, 'spec': pod}}},
        {'apiVersion': 'v1', 'kind': 'Service', 'metadata': meta('hermes-jobs-gpt'),
         'spec': {'selector': labels, 'ports': [{'name': 'http', 'port': 9120, 'targetPort': 9120}]}},
        {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy', 'metadata': meta('hermes-jobs-gpt'),
         'spec': {'podSelector': {'matchLabels': labels}, 'policyTypes': ['Ingress', 'Egress'],
                  'ingress': [{'from': [{'podSelector': {'matchLabels': jobs}}], 'ports': [{'protocol': 'TCP', 'port': 9120}]}],
                  'egress': [{'to': [{'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': 'kube-system'}},
                                      'podSelector': {'matchLabels': {'k8s-app': 'kube-dns'}}}],
                              'ports': [{'protocol': 'UDP', 'port': 53}, {'protocol': 'TCP', 'port': 53}]},
                             {'to': [{'ipBlock': {'cidr': '0.0.0.0/0', 'except': ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16', '127.0.0.0/8', '66.11.126.176/28', '224.0.0.0/4']}}],
                              'ports': [{'protocol': 'TCP', 'port': 443}]}]}},
        {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy', 'metadata': meta('hermes-jobs-to-gpt'),
         'spec': {'podSelector': {'matchLabels': jobs}, 'policyTypes': ['Egress'],
                  'egress': [{'to': [{'podSelector': {'matchLabels': labels}}], 'ports': [{'protocol': 'TCP', 'port': 9120}]}]}}
    ]}
