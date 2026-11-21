"""Own one application cycle process; never owns or terminates Chromium."""
import json
import os
import signal
import subprocess
import sys
import time
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
    if os.environ.get('JOB_SCREENING_MODE','local') == 'openai':
        from openai_screening import configuration_error
        error = configuration_error()
        if error:
            raise ValueError(error)
    if os.environ.get('JOB_SCREENING_MODE','local')=='groq' and (not os.environ.get('GROQ_API_KEY') or os.environ.get('JOB_AI_PROVIDER') != 'groq' or os.environ.get('JOB_SCREENING_SHARING_APPROVED')!='1'):
        raise ValueError('The configured free-plan screening provider is missing')
    old = DATA / 'adapter-run.log'
    if old.exists() and old.stat().st_size > 10 * 1024 * 1024:
        old.replace(old.with_suffix('.previous.log'))
    with old.open('a') as log:
        old.chmod(0o600)
        proc = subprocess.Popen([sys.executable, str(Path(__file__).with_name('naukri_worker.py')), '--execute'],
                                cwd=str(DATA), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
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
        STATE.write_text(json.dumps(data))
        STATE.chmod(0o600)
    return status(app)


def check():
    result = subprocess.run([sys.executable, str(Path(__file__).with_name('naukri_worker.py')), '--check'], cwd=str(DATA),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
    if result.returncode:
        raise ValueError('Application readiness check failed: ' + result.stderr[-350:])
    return {'ready': True, 'started': False, 'engine': 'naukrigulf'}
