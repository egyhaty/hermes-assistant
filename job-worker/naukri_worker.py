"""One finite authenticated search/review/apply cycle using the approved CV."""
import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

from application_journal import Journal
from cdp_browser import BrowserPage
from job_matching import screen
from job_sources import Store, canonical_url, is_uae, search_url
from naukri_adapter import already_applied, inspect_job, submit
from worker_guard import profile_ready_error

DATA = Path(os.environ.get('JOB_DATA', '/data'))
STATE = DATA / '.adapter-run-state.json'
TERMS = ['Linux System Administrator', 'Linux Administrator', 'DevOps Engineer', 'Infrastructure Engineer']
ROLE = re.compile(r'linux|devops|infrastructure|platform|systems? (?:engineer|admin)|site reliability|\bSRE\b', re.I)
OUTSIDE_ROLE = re.compile(r'civil|construction|structural|road|backend|full.?stack|frontend|sales|business analyst|database administrator', re.I)


def state_write(state):
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state))
    tmp.chmod(0o600)
    tmp.replace(STATE)


def search_pages(page, term):
    url = search_url('naukrigulf', term)
    visited = set()
    while url and url not in visited:
        visited.add(url)
        page.goto(url)
        page.wait("document.querySelectorAll('a[href*=\"-jid-\"]').length>0||/security verification|No jobs found/i.test(document.body.innerText)", 20)
        data = page.js('''(()=>{const text=document.body.innerText;if(/security verification|verify you are not a bot/i.test(text.slice(0,1000)))return {challenge:true,jobs:[],next:null};const seen=new Set();const jobs=[];for(const a of document.querySelectorAll('a[href*="-jid-"]')){const title=a.innerText.trim().split('\\n')[0];if(!title||seen.has(a.href))continue;seen.add(a.href);let c=a;for(let i=0;i<7&&c.parentElement&&c.parentElement.tagName!=='BODY';i++){const parent=c.parentElement;const ids=new Set(Array.from(parent.querySelectorAll('a[href*="-jid-"]')).map(x=>x.href));if(ids.size>1||parent.innerText.length>3500)break;c=parent;}jobs.push({source:'naukrigulf',url:a.href,title,card:c.innerText.slice(0,2000)});}const next=Array.from(document.querySelectorAll('a')).find(a=>a.innerText.trim()==='Next'&&a.getBoundingClientRect().height>0);return {challenge:false,jobs,next:next?.href||null};})()''')
        if data['challenge']:
            raise RuntimeError('Naukrigulf requires manual security verification')
        yield data['jobs']
        candidate = data['next']
        if candidate and candidate.startswith('https://www.naukrigulf.com/') and '-jobs-in-uae' in candidate:
            url = candidate
        else:
            url = None


def run(check=False, execute=False, terms=None):
    os.umask(0o077)
    error = profile_ready_error()
    if error:
        raise RuntimeError(error)
    config = json.loads((DATA / 'user_config.json').read_text())
    digest = hashlib.sha256((DATA / 'resume.pdf').read_bytes()).hexdigest()
    journal = Journal(DATA / 'job-applications.sqlite3')
    store = Store(DATA / 'job-discovery.sqlite3')
    state = {'engine': 'naukrigulf', 'running': True, 'started_at': int(time.time()), 'pid': os.getpid(), 'confirmed': 0, 'inspected': 0, 'skipped': 0, 'needs_input': 0, 'uncertain': 0}
    state_write(state)
    lock = open(DATA / '.application-adapter.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    page = BrowserPage('www.naukrigulf.com')
    try:
        page.goto('https://www.naukrigulf.com/mnj/userProfile/myHome')
        page.wait("/Welcome Back|LOGIN|Sign In/i.test(document.body.innerText)", 20)
        if not page.js("document.body.innerText.includes('Welcome Back!')"):
            raise RuntimeError('Sign in to Naukrigulf in the private browser first')
        if check:
            state.update(ready=True, stop_reason='Signed-in browser and approved CV verified; no applications started.')
            return state
        if os.environ.get('JOB_SCREENING_MODE','local')=='groq' and (not os.environ.get('GROQ_API_KEY') or os.environ.get('JOB_AI_PROVIDER') != 'groq' or os.environ.get('JOB_SCREENING_SHARING_APPROVED')!='1'):
            raise RuntimeError('The configured free-plan screening provider is missing')
        known = journal.known_urls()
        seen = set()
        for term in terms or TERMS:
            # Finish collecting a query before navigating away to its listings.
            candidates = []
            for jobs in search_pages(page, term):
                candidates.extend(jobs)
            records = []
            for candidate in candidates:
                url = canonical_url('naukrigulf', candidate['url'])
                if not url or url in seen:
                    continue
                seen.add(url)
                card = candidate['card']
                location = next((line.strip() for line in card.splitlines() if 'United Arab Emirates' in line), '')
                records.append({'source': 'naukrigulf', 'url': url, 'title': candidate['title'], 'company': '', 'location': location,
                                'location_verified': is_uae(location), 'application_status': 'not_applied'})
            store.save({'source': 'naukrigulf', 'term': term, 'status': 'ok' if records else 'unrecognized', 'checked_at': int(time.time()),
                        'search_url': search_url('naukrigulf', term), 'message': f'{len(records)} authenticated listings collected. Applications tracked separately.', 'jobs': records})
            for candidate in records:
                if candidate['url'] in known or not ROLE.search(candidate['title']) or OUTSIDE_ROLE.search(candidate['title']):
                    continue
                job = inspect_job(page, candidate['url'])
                state['inspected'] += 1
                if already_applied(job):
                    journal.review(job, digest, False, 'Already applied on the platform; no repeat submission')
                    state['skipped'] += 1
                    continue
                if not job['easyApply']:
                    journal.review(job, digest, False, 'External or unsupported application flow; not submitted automatically')
                    state['skipped'] += 1
                    continue
                if not is_uae(job['location']):
                    journal.review(job, digest, False, 'UAE job location could not be established')
                    state['skipped'] += 1
                    continue
                decision = screen(config, {k: job[k] for k in ('title', 'company', 'head', 'description')})
                reason = decision['reason'] + (' Gaps: ' + '; '.join(decision['gaps']) if decision['gaps'] else '')
                journal.review(job, digest, decision['eligible'], reason)
                known.add(job['url'])
                if not decision['eligible']:
                    state['skipped'] += 1
                elif execute:
                    # Recheck approval and CV identity immediately before the submit action.
                    if profile_ready_error() or hashlib.sha256((DATA / 'resume.pdf').read_bytes()).hexdigest() != digest:
                        raise RuntimeError('Application profile changed during the run')
                    outcome = submit(page, job, journal, digest)
                    if outcome in state:
                        state[outcome] += 1
                    print('Application outcome: ' + json.dumps({'title': job['title'], 'company': job['company'], 'status': outcome}), flush=True)
                state_write(state)
        state['stop_reason'] = 'Available search results reviewed; only confirmed submissions counted.' if execute else 'Review-only cycle completed; no applications sent.'
        return state
    finally:
        state.update(running=False, finished_at=int(time.time()))
        state_write(state)
        page.close()
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--term', action='append')
    args = parser.parse_args()
    try:
        result = run(args.check, args.execute, args.term)
        print(json.dumps(result), flush=True)
    except Exception as error:
        try:
            old = json.loads(STATE.read_text())
        except (OSError, ValueError):
            old = {}
        attention=('manual security verification' in str(error).lower() or 'sign in to naukrigulf' in str(error).lower() or getattr(error,'status_code',None)==429)
        old.update(running=False, exit_code=0 if attention else 1, attention_required=attention, stop_reason=str(error)[:400], finished_at=int(time.time()))
        state_write(old)
        print('Application cycle stopped: ' + str(error)[:400], file=sys.stderr, flush=True)
        sys.exit(0 if attention else 1)
