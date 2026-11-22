"""Own one application cycle process; never owns or terminates Chromium."""
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

from application_journal import Journal
from worker_guard import profile_ready_error

DATA = Path(os.environ.get('JOB_DATA', '/data'))
STATE = DATA / '.adapter-run-state.json'


def status(app):
    try:
        data = json.loads(STATE.read_text())
    except (OSError, ValueError):
        data = {}
    proc = app.get('adapter_proc')
    running = bool(proc and proc.poll() is None)
    data.update(running=running, pid=proc.pid if running else None, engine='naukrigulf')
    if proc and not running:
        data['exit_code'] = 0 if data.get('cancelled') else proc.returncode
    elif not proc and data.get('started_at') and not data.get('finished_at'):
        data['stop_reason'] = 'Worker restarted. Interrupted submissions need verification; they will not be retried.'
    journal=Journal(DATA / 'job-applications.sqlite3')
    rows = journal.activity()
    counts=journal.counts()
    data['counts'] = {name: counts.get(name,0) for name in ('confirmed', 'eligible', 'skipped', 'needs_input', 'uncertain', 'attempting')}
    data['applications'] = [{k: r[k] for k in ('source', 'job', 'status', 'reason', 'updated', 'attempts')} for r in rows[:100]]
    data['enabled'] = os.environ.get('JOB_APPLICATION_ENGINE') == 'naukrigulf'
    data['screening_mode'] = os.environ.get('JOB_SCREENING_MODE','local')
    if data['screening_mode'] == 'codex':
        from gpt_gateway import validation_status, request
        try: connection = request('/status')
        except ValueError: connection = {'connected': False, 'error': 'GPT connection unavailable'}
        # Device sign-in codes belong only on the dedicated connection page.
        data['gpt'] = {key: connection[key] for key in ('connected', 'model', 'error') if key in connection}
        data['gpt']['validation'] = validation_status()
        data['ready_to_apply'] = bool(connection.get('connected') and data['gpt']['validation'].get('ready'))
    else:
        data['ready_to_apply'] = data['enabled']
    return data


def start(app):
    if os.environ.get('JOB_APPLICATION_ENGINE') != 'naukrigulf':
        raise ValueError('The application adapter is not enabled yet')
    existing = app.get('adapter_proc')
    if existing and existing.poll() is None:
        return dict(status(app), skipped=True)
    error = profile_ready_error()
    if error:
        raise ValueError(error)
    if os.environ.get('JOB_SCREENING_MODE','local') == 'codex':
        from gpt_gateway import readiness_error
        error = readiness_error()
        if error:
            raise ValueError(error)
    if os.environ.get('JOB_SCREENING_MODE','local') == 'openai':
        from openai_screening import configuration_error
        error = configuration_error()
        if error:
            raise ValueError(error)
    if os.environ.get('JOB_SCREENING_MODE','local')=='groq' and (not os.environ.get('GROQ_API_KEY') or os.environ.get('JOB_AI_PROVIDER') != 'groq' or os.environ.get('JOB_SCREENING_SHARING_APPROVED')!='1'):
        raise ValueError('The configured free-plan screening provider is missing')
    run_id = uuid.uuid4().hex
    folder = DATA / 'run-logs'; folder.mkdir(exist_ok=True, mode=0o700)
    log_file = folder / (run_id + '.log')
    with log_file.open('a') as log:
        log_file.chmod(0o600)
        env = dict(os.environ, JOB_RUN_ID=run_id)
        proc = subprocess.Popen([sys.executable, str(Path(__file__).with_name('naukri_worker.py')), '--execute'],
                                cwd=str(DATA), env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    app['adapter_proc'] = proc
    return {'running': True, 'pid': proc.pid, 'engine': 'naukrigulf'}


def stop(app):
    proc = app.get('adapter_proc')
    if proc and proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
        try:
            data = json.loads(STATE.read_text())
        except (OSError, ValueError):
            data = {}
        data.update(running=False, cancelled=True, finished_at=int(time.time()), stop_reason='Stopped by owner. Interrupted submissions require verification.')
        if data.get('run_id'):
            Journal(DATA / 'job-applications.sqlite3').finish_run(data['run_id'], 'cancelled', {key: data.get(key, 0) for key in ('confirmed', 'inspected', 'skipped', 'needs_input', 'uncertain')}, data['stop_reason'])
        STATE.write_text(json.dumps(data))
        STATE.chmod(0o600)
    return status(app)


def check():
    result = subprocess.run([sys.executable, str(Path(__file__).with_name('naukri_worker.py')), '--check'], cwd=str(DATA),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
    if result.returncode:
        raise ValueError('Application readiness check failed: ' + result.stderr[-350:])
    return {'ready': True, 'started': False, 'engine': 'naukrigulf'}
