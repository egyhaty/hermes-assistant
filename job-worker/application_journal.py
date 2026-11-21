"""Durable review/attempt/confirmation records. An uncertain attempt is never retried automatically."""
import json
import os
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

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def review(self, job, cv_sha256, eligible, reason):
        url = canonical_url(job['source'], job['url'])
        if not url or len(cv_sha256) != 64 or not reason.strip():
            raise ValueError('A board job URL, CV digest and review reason are required')
        with self.connect() as db:
            row = db.execute('SELECT status FROM applications WHERE url=?', (url,)).fetchone()
            if row:
                return row[0]
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

    def known_urls(self):
        with self.connect() as db:
            return {row[0] for row in db.execute('SELECT url FROM applications')}

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
