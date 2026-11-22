"""Worker client for the private self-hosted GPT matcher, never a browser service."""
import fcntl
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = 'http://hermes-jobs-gpt.hermes.svc.cluster.local:9120'
DATA = Path(os.environ.get('JOB_DATA', '/data'))


def request(path, payload=None):
    token = os.environ.get('GPT_MATCHER_TOKEN')
    if not token: raise ValueError('The private GPT connection has not been configured')
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode() if payload is not None else None,
                                 method='POST' if payload is not None else 'GET',
                                 headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=125 if path == '/match' else 20) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try: message = json.load(error).get('error', 'GPT service unavailable')
        except (ValueError, OSError): message = 'GPT service unavailable'
        raise ValueError(str(message)[:240]) from None
    except (urllib.error.URLError, TimeoutError):
        raise ValueError('The self-hosted GPT service is temporarily unavailable') from None


def calibration_key():
    from worker_guard import profile_digest
    return hashlib.sha256(('gpt-6.2-sol\nfit-checks-v1\n' + profile_digest()).encode()).hexdigest()


def validation_status():
    try: state = json.loads((DATA / 'gpt-validation.json').read_text())
    except (OSError, ValueError): return {'status': 'pending', 'ready': False}
    try: current = state.get('profile_key') == calibration_key()
    except OSError: current = False
    return dict(state, ready=current and state.get('status') == 'passed')


def readiness_error():
    if os.environ.get('JOB_SCREENING_SHARING_APPROVED') != '1':
        return 'Professional-summary sharing with GPT is not enabled'
    try: status = request('/status')
    except ValueError as error: return str(error)
    if not status.get('connected'): return 'Connect ChatGPT from the jobs workspace to enable GPT matching'
    if not validation_status().get('ready'): return 'GPT fit checks must pass before automatic applications start'
    return None


def ensure_validated(retry=False):
    from job_matching import screen
    from calibrate_screening import CASES
    from worker_guard import profile_ready_error
    error = profile_ready_error()
    if error: raise ValueError(error)
    connection = request('/status')
    if not connection.get('connected'): return {'status': 'needs_auth', 'ready': False}
    old = validation_status()
    if old.get('ready'): return old
    if old.get('status') == 'failed' and not retry: return old
    with (DATA / '.gpt-validation.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return {'status': 'checking', 'ready': False}
        state = {'status': 'checking', 'ready': False, 'profile_key': calibration_key(), 'model': connection['model'],
                 'started_at': int(time.time()), 'results': [], 'applications_submitted': 0}
        target = DATA / 'gpt-validation.json'
        def save():
            tmp = target.with_suffix('.tmp'); tmp.write_text(json.dumps(state)); tmp.chmod(0o600); tmp.replace(target)
        save()
        config = json.loads((DATA / 'user_config.json').read_text())
        try:
            for name, expected, title, description in CASES:
                start = time.monotonic()
                decision = screen(config, {'title': title, 'company': 'Synthetic validation company', 'head': title + '\nDubai, UAE', 'description': description})
                state['results'].append({'case': name, 'passed': decision['eligible'] is expected,
                                         'seconds': round(time.monotonic() - start, 2), 'decision': decision})
                save()
            state['status'] = 'passed' if all(row['passed'] for row in state['results']) else 'failed'
            state['ready'] = state['status'] == 'passed'
        except Exception:
            state.update(status='failed', ready=False, error='GPT validation did not finish; automatic submission remains on hold.')
        state['finished_at'] = int(time.time()); save()
        return state
