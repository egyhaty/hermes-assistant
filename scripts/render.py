#!/usr/bin/env python3
"""Render a stopped Kubernetes deployment from non-secret settings."""
import argparse
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]

def render(settings, root=ROOT):
    required = {'namespace', 'image', 'provider', 'model', 'timezone', 'storage_class', 'storage_size', 'secret_name'}
    if not required.issubset(settings) or set(settings) - required - {'image_pull_secret', 'dashboard', 'dashboard_host'} or not all(isinstance(v, str) for v in settings.values()):
        raise ValueError('settings must contain exactly the documented string fields')
    if 'REQUIRED_' in json.dumps(settings):
        raise ValueError('fill required deployment values first')
    for key in ['namespace', 'secret_name'] + (['image_pull_secret'] if settings.get('image_pull_secret') else []):
        if len(settings[key]) > 63 or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', settings[key]):
            raise ValueError('invalid Kubernetes name: ' + key)
    if not re.fullmatch(r'[A-Za-z0-9./_:-]+@sha256:[0-9a-f]{64}', settings['image']):
        raise ValueError('image must be pinned by sha256 digest')
    if not re.fullmatch(r'[1-9][0-9]*(?:Gi|Mi)', settings['storage_size']):
        raise ValueError('storage_size must be a positive Mi or Gi quantity')
    if settings['provider'] not in ('openai-codex', 'openrouter'):
        raise ValueError('only the authorized subscription or free OpenRouter provider is allowed')
    if settings['provider'] == 'openrouter' and settings['model'] != 'openrouter/free' and not settings['model'].endswith(':free'):
        raise ValueError('OpenRouter must use a free-only model; paid models are refused')
    if not settings['model'].strip():
        raise ValueError('provider and model must be chosen explicitly')
    if settings.get('dashboard', 'disabled') not in ('enabled', 'disabled'):
        raise ValueError('dashboard must be enabled or disabled')
    if settings.get('dashboard_host'):
        host = settings['dashboard_host']
        if settings.get('dashboard') != 'enabled' or len(host) > 253 or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host) or '..' in host or '.' not in host:
            raise ValueError('dashboard_host requires an enabled dashboard and a valid DNS hostname')
    ZoneInfo(settings['timezone'])
    ns = settings['namespace']
    labels = {'app.kubernetes.io/name': 'hermes-karem'}
    metadata = lambda name: {'name': name, 'namespace': ns, 'labels': labels}
    config = {
        '_config_version': 51,  # Verified against the selected Hermes v0.22.5 image.
        'model': {'provider': settings['provider'], 'default': settings['model']},
        'database': {'journal_mode': 'delete'},
        'plugins': {'enabled': ['langfuse'], 'entries': {'langfuse': {'settings': {'end_user_attribution': False}}}},
        'agent': {'max_turns': 5 if settings['provider'] == 'openrouter' else 30, 'gateway_timeout': 900},
        'max_concurrent_sessions': 2,
        'group_sessions_per_user': True,
        'web': {'backend': 'firecrawl', 'search_backend': 'firecrawl', 'extract_backend': 'firecrawl'},
        'kanban': {'dispatch_in_gateway': False, 'review_dispatch': False,
                   'notify_in_gateway': False, 'auto_subscribe_on_create': False},
        'terminal': {'backend': 'local', 'cwd': '/opt/data/workspace', 'timeout': 120, 'home_mode': 'profile'},
        'memory': {'memory_enabled': True, 'user_profile_enabled': True,
                   'memory_char_limit': 2200, 'user_char_limit': 1800, 'nudge_interval': 10},
        'compression': {'enabled': True},
        'skills': {'external_dirs': ['/opt/karem/skills'], 'creation_nudge_interval': 0},
        # No cron, delegation, mail/calendar write, MCP or messaging toolsets in initial profile.
        'platform_toolsets': {surface: ['web', 'terminal', 'file', 'skills', 'todo',
            'memory', 'session_search', 'clarify'] for surface in ['cli', 'telegram']},
        'platforms': {'telegram': {'extra': {'drop_pending_on_cold_boot': True,
                                             'disable_link_previews': True,
                                             'unauthorized_dm_behavior': 'ignore'}}},
    }
    pvc_spec = {'accessModes': ['ReadWriteOnce'], 'resources': {'requests': {'storage': settings['storage_size']}}}
    if settings['storage_class']:
        pvc_spec['storageClassName'] = settings['storage_class']
    container = {
        'name': 'hermes', 'image': settings['image'], 'imagePullPolicy': 'IfNotPresent',
        'envFrom': [{'secretRef': {'name': settings['secret_name']}},
                    {'secretRef': {'name': 'hermes-langfuse', 'optional': True}}],
        'env': [{'name': 'HERMES_HOME', 'value': '/opt/data'}, {'name': 'HOME', 'value': '/opt/data'},
                {'name': 'HERMES_TIMEZONE', 'value': settings['timezone']},
                {'name': 'HERMES_LANGFUSE_CAPTURE', 'value': 'metadata'},
                {'name': 'TZ', 'value': settings['timezone']},
                {'name': 'HIMALAYA_CONFIG', 'value': '/opt/data/workspace/himalaya-config/config.toml'}],
        'resources': {'requests': {'cpu': '250m', 'memory': '1Gi'},
                      'limits': {'cpu': '2', 'memory': '4Gi'}},
        'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                            'capabilities': {'drop': ['ALL']}},
        'volumeMounts': [{'name': 'data', 'mountPath': '/opt/data', 'subPath': 'hermes-home'},
                         {'name': 'managed', 'mountPath': '/etc/karem', 'readOnly': True},
                         {'name': 'tmp', 'mountPath': '/tmp'},
                         {'name': 'private', 'mountPath': '/etc/karem-private', 'readOnly': True},
                         {'name': 'mail', 'mountPath': '/etc/hermes-mail', 'readOnly': True}],
        # Process-only readiness: not a claim that Telegram/provider connectivity is healthy.
        'readinessProbe': {'exec': {'command': ['/opt/hermes/.venv/bin/python', '-c',
            "from pathlib import Path; import sys; sys.exit(0 if b'gateway' in Path('/proc/1/cmdline').read_bytes() else 1)"]},
            'initialDelaySeconds': 10, 'periodSeconds': 15, 'timeoutSeconds': 5},
    }
    if settings['provider'] == 'openrouter':
        config['model'].update(base_url='https://openrouter.ai/api/v1', api_mode='chat_completions')
        config['auxiliary'] = {'free_only': True}
        container['envFrom'].append({'secretRef': {'name': 'hermes-free-api'}})
    init_code = """from pathlib import Path
import os
root = Path('/mnt/pvc')
home = root / 'hermes-home'
if home.is_symlink():
    raise SystemExit('refusing a symlink data directory')
legacy = [p.name for p in root.iterdir() if p.name not in ('lost+found', 'hermes-home')]
if legacy:
    raise SystemExit('Legacy PVC-root data must be migrated offline before startup')
os.umask(0o077)
home.mkdir(mode=0o700, exist_ok=True)
if home.stat().st_uid != os.getuid():
    raise SystemExit('Hermes data directory must be owned by the runtime UID')
"""
    init = {'name': 'prepare-data-home', 'image': settings['image'],
            'command': ['/opt/hermes/.venv/bin/python', '-c', init_code],
            'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                                'capabilities': {'drop': ['ALL']}},
            'resources': {'requests': {'cpu': '25m', 'memory': '32Mi'},
                          'limits': {'cpu': '250m', 'memory': '128Mi'}},
            'volumeMounts': [{'name': 'data', 'mountPath': '/mnt/pvc'}]}
    deployment = {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': metadata('hermes'),
        'spec': {'replicas': 0, 'strategy': {'type': 'Recreate'}, 'selector': {'matchLabels': labels},
                 'template': {'metadata': {'labels': labels}, 'spec': {
                    'automountServiceAccountToken': False, 'terminationGracePeriodSeconds': 60,
                    'securityContext': {'runAsNonRoot': True, 'runAsUser': 10000, 'runAsGroup': 10000,
                        'fsGroup': 10000, 'fsGroupChangePolicy': 'OnRootMismatch',
                        'seccompProfile': {'type': 'RuntimeDefault'}},
                    'initContainers': [init], 'containers': [container],
                    'volumes': [{'name': 'data', 'persistentVolumeClaim': {'claimName': 'hermes-data'}},
                                {'name': 'managed', 'configMap': {'name': 'hermes-managed'}},
                                {'name': 'tmp', 'emptyDir': {'sizeLimit': '1Gi'}},
                                {'name': 'private', 'secret': {'secretName': 'hermes-profile', 'defaultMode': 288}},
                                {'name': 'mail', 'secret': {'secretName': 'hermes-gmail', 'optional': True, 'defaultMode': 288}}]}}}}
    if settings.get('dashboard') == 'enabled':
        # Admin UI explicitly manages the same profile; no Telegram/API/profile Secret is injected.
        dashboard = {
            'name': 'dashboard', 'image': settings['image'], 'imagePullPolicy': 'IfNotPresent',
            'command': ['/opt/hermes/.venv/bin/hermes', 'dashboard', '--host', '0.0.0.0',
                        '--port', '9119', '--no-open', '--skip-build'],
            'envFrom': [{'secretRef': {'name': 'hermes-dashboard-auth'}}],
            'env': [{'name': 'HOME', 'value': '/opt/data'}, {'name': 'HERMES_HOME', 'value': '/opt/data'},
                    {'name': 'TZ', 'value': settings['timezone']}],
            'volumeMounts': [{'name': 'data', 'mountPath': '/opt/data', 'subPath': 'hermes-home'},
                             {'name': 'dashboard-tmp', 'mountPath': '/tmp'}],
            'resources': {'requests': {'cpu': '100m', 'memory': '256Mi'},
                          'limits': {'cpu': '1', 'memory': '1Gi'}},
            'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                                'capabilities': {'drop': ['ALL']}},
            'readinessProbe': {'tcpSocket': {'port': 9119}, 'initialDelaySeconds': 20,
                              'periodSeconds': 15, 'timeoutSeconds': 5},
        }
        if settings.get('dashboard_host'):
            dashboard['env'].append({'name': 'HERMES_DASHBOARD_PUBLIC_URL', 'value': 'https://' + settings['dashboard_host']})
        deployment['spec']['template']['spec']['containers'].append(dashboard)
        deployment['spec']['template']['spec']['volumes'].append(
            {'name': 'dashboard-tmp', 'emptyDir': {'sizeLimit': '512Mi'}})
    if settings.get('image_pull_secret'):
        deployment['spec']['template']['spec']['imagePullSecrets'] = [{'name': settings['image_pull_secret']}]
    objects = [
        {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': ns, 'labels': {'pod-security.kubernetes.io/enforce': 'restricted', 'pod-security.kubernetes.io/enforce-version': 'v1.36'}}},
        {'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim', 'metadata': {**metadata('hermes-data'), 'annotations': {'argocd.argoproj.io/sync-options': 'Prune=false,Delete=false'}}, 'spec': pvc_spec},
        {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': metadata('hermes-managed'), 'data': {
            'config.yaml': json.dumps(config, indent=2), 'SOUL.md': (root / 'config/SOUL.md').read_text()}},
        deployment,
        {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy', 'metadata': metadata('hermes-ingress'),
         'spec': {'podSelector': {}, 'policyTypes': ['Ingress'], 'ingress': []}},
    ]
    return {'apiVersion': 'v1', 'kind': 'List', 'items': objects}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', required=True, type=Path)
    parser.add_argument('--out', type=Path, default=ROOT / 'build')
    args = parser.parse_args()
    try:
        result = render(json.loads(args.settings.read_text()))
        args.out.mkdir(parents=True, exist_ok=True)
        target = args.out / 'manifest.json'
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print('Rendered ' + str(target) + '; replicas=0, nothing applied')
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, str(error) + '\n')

if __name__ == '__main__':
    main()
