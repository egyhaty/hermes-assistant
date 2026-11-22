"""Run supported board adapters sequentially on the private server browser."""
import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

DATA = Path(os.environ.get('JOB_DATA', '/data'))
COUNTS = ('confirmed', 'inspected', 'skipped', 'needs_input', 'uncertain')


def sources():
    selected = os.environ.get('JOB_ACTIVE_SOURCES', 'naukrigulf').split(',')
    selected = list(dict.fromkeys(x.strip() for x in selected if x.strip()))
    if not selected or any(x not in ('naukrigulf', 'linkedin', 'bayt', 'gulftalent', 'indeed') for x in selected):
        raise ValueError('Choose supported, verified application adapters')
    return selected


def cv_sync_error(source):
    import hashlib
    try:
        state = json.loads((DATA / 'reviewed-cv-sync.json').read_text())
        digest = hashlib.sha256((DATA / 'resume.pdf').read_bytes()).hexdigest()
        synced = next((x for x in state['sites'] if x['source'] == source), {})
        if not synced.get('persisted') or synced.get('sha256') != digest:
            return 'The reviewed CV must be synchronized with ' + source + ' before applications start'
    except (OSError, ValueError, KeyError):
        return 'The reviewed CV has not been verified on ' + source
    return None


def main(check=False):
    from worker_guard import profile_ready_error
    error = profile_ready_error()
    if error: raise ValueError(error)
    if check:
        if os.environ.get('JOB_SCREENING_MODE') == 'codex':
            from gpt_gateway import readiness_error
            error = readiness_error()
            if error: raise ValueError(error)
        available = [source for source in sources() if not cv_sync_error(source)]
        print(json.dumps({'ready': bool(available), 'started': False, 'sources': available,
                          'authentication_checked_on_each_run': True}), flush=True)
        return 0 if available else 1
    batch = os.environ.get('JOB_RUN_ID') or uuid.uuid4().hex
    state = {'engine': 'multisite', 'run_id': batch, 'running': True, 'pid': os.getpid(), 'started_at': int(time.time()),
             'sources': [], **{key: 0 for key in COUNTS}}
    state_file = DATA / '.adapter-run-state.json'
    logs = DATA / 'run-logs'; logs.mkdir(exist_ok=True, mode=0o700)
    ready = 0
    for source in sources():
        error = cv_sync_error(source)
        if error:
            state['sources'].append({'source': source, 'status': 'attention_required', 'reason': error})
            continue
        tracks = ['devops_uae']
        if source == 'linkedin' and os.environ.get('JOB_HOSTING_REMOTE') == '1': tracks.append('hosting_remote')
        for track in tracks:
            child = uuid.uuid4().hex
            env = dict(os.environ, JOB_RUN_ID=child)
            command = [sys.executable, str(Path(__file__).with_name('naukri_worker.py')), '--source', source,
                       '--track', track, '--check' if check else '--execute']
            log_file = logs / (child + '.log')
            with log_file.open('a') as output:
                log_file.chmod(0o600)
                result = subprocess.run(command, env=env, cwd=str(DATA), stdout=output, stderr=subprocess.STDOUT)
            try: outcome = json.loads(state_file.read_text())
            except (OSError, ValueError): outcome = {}
            if outcome.get('run_id') != child: outcome = {}
            state['sources'].append({'source': source, 'track': track, 'run_id': child, 'exit_code': result.returncode,
                                     'reason': outcome.get('stop_reason', 'Source cycle failed before initialization')})
            for key in COUNTS: state[key] += outcome.get(key, 0)
            if not result.returncode and not outcome.get('attention_required') and outcome.get('ready' if check else 'finished_at'): ready += 1
            print(json.dumps({'source': source, 'track': track, 'run_id': child, 'counts': {key: outcome.get(key, 0) for key in COUNTS},
                              'reason': outcome.get('stop_reason', '')}), flush=True)
    state.update(running=False, finished_at=int(time.time()), ready=ready > 0,
                 stop_reason='Supported site cycles finished; review individual results and required inputs.')
    temp = state_file.with_suffix('.tmp'); temp.write_text(json.dumps(state)); temp.chmod(0o600); temp.replace(state_file)
    print(json.dumps(state), flush=True)
    return 0 if ready else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try: raise SystemExit(main(args.check))
    except (ValueError, OSError) as error:
        print('Application batch held: ' + str(error)[:350], file=sys.stderr)
        raise SystemExit(1)
