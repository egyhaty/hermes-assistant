"""Owner-only reports: discoveries, submissions, screening audits and Dubai timestamps."""
import csv
import io
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

DUBAI = ZoneInfo('Asia/Dubai')


def dubai_time(stamp):
    return datetime.fromtimestamp(stamp, DUBAI).isoformat() if stamp else ''


def summary(journal):
    records = journal.report_records()
    counts = Counter(row['status'] for row in records)
    daily = {}
    audits = 0
    for row in records:
        day = dubai_time(row['updated'])[:10]
        item = daily.setdefault(day, {'date': day, 'confirmed': 0, 'skipped': 0, 'needs_input': 0, 'uncertain': 0})
        if row['status'] in item: item[row['status']] += 1
        if row['status'] == 'confirmed' and row['job'].get('screening_audit', {}).get('verified_fit') is False:
            audits += 1
    return {'timezone': 'Asia/Dubai', 'counts': dict(counts), 'confirmed_with_fit_audit': audits,
            'daily': sorted(daily.values(), key=lambda row: row['date'], reverse=True)[:30],
            'runs': journal.run_history(),
            'cv_variants': [{'company': r['job'].get('company', ''), 'title': r['job'].get('title', ''),
                             'status': r['status'], **r['job']['resume_tailoring']}
                            for r in records if r['job'].get('resume_tailoring')][-100:]}


def safe_cell(value):
    value = str(value if value is not None else '')
    return "'" + value if value.startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value


def applications_csv(journal):
    out = io.StringIO(); writer = csv.writer(out)
    writer.writerow(['Updated (Dubai)', 'Site', 'Track', 'Company', 'Role', 'Location', 'Status', 'Attempts', 'Reason', 'Fit audit', 'CV variant', 'CV delivery', 'URL'])
    for row in journal.report_records():
        job = row['job']
        writer.writerow([safe_cell(value) for value in (dubai_time(row['updated']), row['source'], job.get('track', 'devops_uae'), job.get('company', ''), job.get('title', ''),
                         job.get('location', ''), row['status'], row['attempts'], row['reason'],
                         job.get('screening_audit', {}).get('reason', ''), job.get('resume_tailoring', {}).get('artifact', ''),
                         job.get('resume_tailoring', {}).get('delivery', 'profile_cv'), row['url'])])
    return '\ufeff' + out.getvalue()


def runs_csv(journal):
    out = io.StringIO(); writer = csv.writer(out)
    writer.writerow(['Run', 'Started (Dubai)', 'Finished (Dubai)', 'Engine', 'Matching', 'Status', 'Reviewed', 'Confirmed', 'Skipped', 'Needs input', 'Uncertain', 'Reason'])
    for row in journal.run_history():
        count = row['counts']
        writer.writerow([safe_cell(value) for value in (row['id'], dubai_time(row['started']), dubai_time(row['finished']), row['engine'], row['provider'], row['status'],
                         count.get('inspected', 0), count.get('confirmed', 0), count.get('skipped', 0), count.get('needs_input', 0), count.get('uncertain', 0), row['reason'])])
    return '\ufeff' + out.getvalue()
