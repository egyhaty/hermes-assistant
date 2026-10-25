#!/usr/bin/env python3
"""Enter a bot token privately, verify the owner via Start, and create its Secret."""
import argparse
import getpass
import json
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.request


class SetupError(Exception):
    pass


def telegram(token, method, payload=None):
    request = urllib.request.Request(
        'https://api.telegram.org/bot' + token + '/' + method,
        data=json.dumps(payload or {}).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            result = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError):
        # Never expose the request URL: Telegram embeds the credential in it.
        raise SetupError('Telegram request failed; check the token/network and retry.') from None
    if not isinstance(result, dict) or result.get('ok') is not True:
        raise SetupError('Telegram rejected the request; check the token or another active poller.')
    return result['result']


def owner_from_update(update, nonce):
    message = update.get('message') if isinstance(update, dict) else None
    if not isinstance(message, dict):
        return None
    user, chat = message.get('from', {}), message.get('chat', {})
    if not isinstance(user, dict) or not isinstance(chat, dict):
        return None
    owner = user.get('id')
    if (type(owner) is not int or owner <= 0 or user.get('is_bot') is not False
            or chat.get('type') != 'private' or type(chat.get('id')) is not int
            or chat['id'] != owner or message.get('forward_origin')
            or message.get('forward_from') or message.get('via_bot')):
        return None
    if message.get('text') not in (nonce, '/start ' + nonce):
        return None
    return owner


def discover_owner(token):
    me = telegram(token, 'getMe')
    username = me.get('username', '')
    if me.get('is_bot') is not True or not re.fullmatch(r'[A-Za-z0-9_]{5,32}', username):
        raise SetupError('Unexpected bot identity; nothing changed.')
    if telegram(token, 'getWebhookInfo').get('url'):
        raise SetupError('This bot already has a webhook. Use a dedicated new bot; no webhook was changed.')
    nonce = 'hermes_' + secrets.token_urlsafe(12)
    print('\nOpen this link in YOUR Telegram account and press Start:')
    print('https://t.me/' + username + '?start=' + nonce, flush=True)
    print('Waiting up to five minutes for that private Start message...', flush=True)
    deadline, offset = time.monotonic() + 300, None
    while time.monotonic() < deadline:
        payload = {'timeout': 20, 'allowed_updates': ['message'], 'limit': 100}
        if offset is not None:
            payload['offset'] = offset
        updates = telegram(token, 'getUpdates', payload)
        for update in updates:
            owner = owner_from_update(update, nonce)
            if owner:
                print('Verified numeric owner ID:', owner)
                return owner
            if isinstance(update, dict) and type(update.get('update_id')) is int:
                offset = max(offset or 0, update['update_id'] + 1)
    raise SetupError('Owner verification timed out; no Secret was created. Run again for a new link.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', default='kubernetes-admin@kubernetes')
    parser.add_argument('--owner-id', type=int, help='Optional known positive numeric owner ID')
    args = parser.parse_args()
    if args.owner_id is not None and args.owner_id <= 0:
        raise SetupError('Owner ID must be positive.')
    check = subprocess.run(
        ['kubectl', '--context', args.context, 'get', 'deployment', 'hermes', '-n', 'hermes', '-o', 'json'],
        text=True, capture_output=True)
    if check.returncode:
        raise SetupError('Cannot inspect the Hermes Deployment; check Kubernetes access.')
    if json.loads(check.stdout).get('spec', {}).get('replicas', 1) != 0:
        raise SetupError('Hermes must be at zero replicas during onboarding; nothing was changed.')
    token = getpass.getpass('Telegram bot token from BotFather (not printed): ').strip()
    if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
        raise SetupError('No valid bot token supplied; nothing changed.')
    owner = args.owner_id if args.owner_id is not None else discover_owner(token)
    obj = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'hermes-credentials', 'namespace': 'hermes'},
           'type': 'Opaque', 'stringData': {'TELEGRAM_BOT_TOKEN': token, 'TELEGRAM_ALLOWED_USERS': str(owner)}}
    applied = subprocess.run(
        ['kubectl', '--context', args.context, 'apply', '--server-side', '--field-manager=hermes-owner', '-f', '-'],
        input=json.dumps(obj), text=True, capture_output=True)
    if applied.returncode:
        raise SetupError('Kubernetes refused the Secret. Credential values were not printed or saved to a file.')
    print(applied.stdout.strip())
    print('Telegram configured. Gateway remains inactive pending acceptance.')


if __name__ == '__main__':
    try:
        main()
    except (SetupError, KeyboardInterrupt) as error:
        raise SystemExit(str(error) or 'Setup cancelled; no credential values printed.') from None
