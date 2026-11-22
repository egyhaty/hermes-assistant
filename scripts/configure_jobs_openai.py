"""Validate and provision a dedicated OpenAI key without printing it or activating jobs."""
import getpass
import json
import subprocess
import urllib.error
import urllib.request

KUBE = ['/usr/local/bin/kubectl', '--context', 'kubernetes-admin@kubernetes', '--request-timeout=20s']


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    context = subprocess.run(KUBE + ['config', 'view', '--minify', '-o', 'json'], text=True, capture_output=True, timeout=25)
    if context.returncode:
        raise SystemExit('Could not verify Kubernetes context; nothing changed.')
    config = json.loads(context.stdout)
    if config.get('current-context') != 'kubernetes-admin@kubernetes' or config['clusters'][0]['cluster']['server'] != 'https://66.11.126.179:6443':
        raise SystemExit('Unexpected Kubernetes target; nothing changed.')
    key = getpass.getpass('Dedicated OpenAI project API key (hidden): ').strip()
    if not key or any(char.isspace() for char in key):
        raise SystemExit('Invalid key input; nothing changed.')
    req = urllib.request.Request('https://api.openai.com/v1/models/gpt-6.2-sol', headers={'Authorization': 'Bearer ' + key, 'User-Agent': 'hermes-openai-setup/1.0'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=25) as response:
            model = json.load(response)
        if model.get('id') != 'gpt-6.2-sol':
            raise ValueError()
    except Exception:
        raise SystemExit('OpenAI credential/model verification failed; nothing changed. Secret details withheld.') from None
    obj = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'hermes-jobs-openai', 'namespace': 'hermes'},
           'type': 'Opaque', 'stringData': {'OPENAI_API_KEY': key}}
    result = subprocess.run(KUBE + ['apply', '--server-side', '--field-manager=hermes-owner', '-f', '-'],
                            input=json.dumps(obj), capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise SystemExit('OpenAI credential write failed; details withheld.')
    print('Secret/hermes-jobs-openai saved. No inference request or provider switch was made.')


if __name__ == '__main__':
    main()
