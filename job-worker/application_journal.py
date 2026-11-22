"""Durable review/attempt/confirmation records. An uncertain attempt is never retried automatically."""
import json
import os
import re
import sqlite3
import time
from pathlib import Path

from job_sources import canonical_url

TERMINAL = {'confirmed', 'already_applied', 'uncertain', 'needs_input', 'skipped'}


class Journal:
    def __init__(self, path):
        os.umask(0o077)
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS applications (url TEXT PRIMARY KEY, source TEXT NOT NULL, job TEXT NOT NULL, cv_sha256 TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL, evidence TEXT NOT NULL DEFAULT "", attempts INTEGER NOT NULL DEFAULT 0, updated INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS application_runs (id TEXT PRIMARY KEY, engine TEXT NOT NULL, provider TEXT NOT NULL, started INTEGER NOT NULL, finished INTEGER, status TEXT NOT NULL, counts TEXT NOT NULL, reason TEXT NOT NULL, log_file TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def review(self, job, cv_sha256, eligible, reason):
        url = canonical_url(job['source'], job['url'])
        if not url or len(cv_sha256) != 64 or not reason.strip():
            raise ValueError('A board job URL, CV digest and review reason are required')
        with self.connect() as db:
            row = db.execute('SELECT status,attempts,job,cv_sha256 FROM applications WHERE url=?', (url,)).fetchone()
            if row:
                previous = json.loads(row[2]).get('screening')
                current = job.get('screening')
                # Reconsider only an unattempted rejection by another matcher.
                reconsider = row[0] == 'skipped' and row[1] == 0 and current and current.get('provider') in ('codex', 'openai') and (row[3] != cv_sha256 or previous and previous.get('provider', 'local') != current.get('provider'))
                if not reconsider: return row[0]
                status = 'eligible' if eligible else 'skipped'
                db.execute('UPDATE applications SET job=?,cv_sha256=?,status=?,reason=?,updated=? WHERE url=? AND status="skipped" AND attempts=0',
                           (json.dumps(dict(job, url=url)), cv_sha256, status, reason, int(time.time()), url))
                return status
            status = 'eligible' if eligible else 'skipped'
            db.execute('INSERT INTO applications (url,source,job,cv_sha256,status,reason,updated) VALUES (?,?,?,?,?,?,?)',
                       (url, job['source'], json.dumps(dict(job, url=url)), cv_sha256, status, reason, int(time.time())))
            return status

    def claim(self, url, cv_sha256):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            result = db.execute('UPDATE applications SET status="attempting",attempts=attempts+1,updated=? WHERE url=? AND status="eligible" AND cv_sha256=?',
                                (int(time.time()), url, cv_sha256))
            return result.rowcount == 1

    def finish(self, url, status, reason, evidence=''):
        if status not in TERMINAL or not reason.strip():
            raise ValueError('A final outcome and reason are required')
        if status == 'confirmed' and not evidence.strip():
            raise ValueError('A submission confirmation requires platform evidence')
        with self.connect() as db:
            result = db.execute('UPDATE applications SET status=?,reason=?,evidence=?,updated=? WHERE url=? AND status="attempting"',
                                (status, reason, evidence[:2000], int(time.time()), url))
            if result.rowcount != 1:
                raise ValueError('No matching active attempt')

    def snapshot(self):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute('SELECT * FROM applications ORDER BY updated DESC LIMIT 500').fetchall()
            return [dict(row, job=json.loads(row['job'])) for row in rows]

    def counts(self):
        with self.connect() as db:
            return dict(db.execute('SELECT status,COUNT(*) FROM applications GROUP BY status'))

    def known_urls(self, provider=None, cv_sha256=None):
        with self.connect() as db:
            known = set()
            for url, status, attempts, raw, previous_cv in db.execute('SELECT url,status,attempts,job,cv_sha256 FROM applications'):
                screening = json.loads(raw).get('screening')
                if provider in ('codex', 'openai') and status == 'skipped' and attempts == 0 and ((cv_sha256 and previous_cv != cv_sha256) or screening and screening.get('provider', 'local') != provider):
                    continue
                known.add(url)
            return known

    def activity(self, limit=100):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute('SELECT * FROM applications WHERE status!="skipped" ORDER BY updated DESC LIMIT ?', (limit,)).fetchall()
            return [dict(row, job=json.loads(row['job'])) for row in rows]

    def reconcile_confirmation(self, url, cv_sha256, evidence):
        """Record independently verified platform evidence after a tracker interruption.

        This never sends another application or resets the attempt counter.
        """
        if not evidence.strip():
            raise ValueError('Independent confirmation evidence is required')
        with self.connect() as db:
            result = db.execute('UPDATE applications SET status="confirmed",reason=?,evidence=?,updated=? WHERE url=? AND cv_sha256=? AND status IN ("attempting","uncertain") AND attempts=1',
                                ('Platform confirmation independently verified after tracking interruption', evidence[:2000], int(time.time()), url, cv_sha256))
            if result.rowcount != 1:
                raise ValueError('No matching interrupted attempt to reconcile')

    def start_run(self, run_id, engine, provider):
        with self.connect() as db:
            db.execute('INSERT INTO application_runs (id,engine,provider,started,status,counts,reason,log_file) VALUES (?,?,?,?,?,?,?,?)',
                       (run_id, engine, provider, int(time.time()), 'running', '{}', '', run_id + '.log'))

    def attach_proof(self, url, filename):
        if not re.fullmatch(r'[a-z0-9-]+\.png', filename): raise ValueError('Invalid proof filename')
        with self.connect() as db:
            row = db.execute('SELECT job FROM applications WHERE url=? AND status IN ("attempting","confirmed")', (url,)).fetchone()
            if not row: raise ValueError('No active or confirmed application for this proof')
            job = json.loads(row[0]); job['proof'] = filename
            db.execute('UPDATE applications SET job=? WHERE url=?', (json.dumps(job), url))

    def finish_run(self, run_id, status, counts, reason):
        if status not in ('completed', 'failed', 'attention_required', 'cancelled', 'interrupted'):
            raise ValueError('Invalid run outcome')
        with self.connect() as db:
            db.execute('UPDATE application_runs SET finished=?,status=?,counts=?,reason=? WHERE id=? AND finished IS NULL',
                       (int(time.time()), status, json.dumps(counts), str(reason)[:400], run_id))

    def run_history(self):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            return [dict(row, counts=json.loads(row['counts'])) for row in db.execute('SELECT * FROM application_runs ORDER BY started DESC LIMIT 100')]

    def recover_interrupted_runs(self):
        """Called only after the worker's exclusive startup lock has been acquired."""
        with self.connect() as db:
            now = int(time.time())
            db.execute('UPDATE application_runs SET finished=?,status="interrupted",reason=? WHERE finished IS NULL',
                       (now, 'Worker restarted; interrupted submissions require verification'))
            db.execute('UPDATE applications SET status="uncertain",reason=?,updated=? WHERE status="attempting"',
                       ('Worker restarted during the attempt; automatic retry disabled', now))

    def report_records(self):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            return [dict(row, job=json.loads(row['job'])) for row in db.execute('SELECT url,source,job,status,reason,attempts,updated FROM applications ORDER BY updated DESC')]
