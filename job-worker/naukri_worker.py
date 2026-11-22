"""One finite authenticated search/review/apply cycle using the approved CV."""
import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import time
import uuid
from functools import partial
from pathlib import Path

from application_journal import Journal
from cdp_browser import BrowserPage
from job_matching import screen
from job_sources import Store, canonical_url, is_uae, search_url
from naukri_adapter import already_applied, inspect_job, submit
from worker_guard import profile_ready_error

DATA = Path(os.environ.get('JOB_DATA', '/data'))
STATE = DATA / '.adapter-run-state.json'
TERMS = ['Linux System Administrator', 'Linux Administrator', 'Linux Support Engineer', 'Hosting Support Engineer', 'DevOps Engineer', 'Infrastructure Engineer']
ROLE = re.compile(r'linux|devops|infrastructure|platform|hosting|cpanel|wordpress|systems? (?:engineer|admin)|site reliability|\bSRE\b', re.I)
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
        data = page.read('''(()=>{const text=document.body.innerText;if(/security verification|verify you are not a bot/i.test(text.slice(0,1000)))return {challenge:true,jobs:[],next:null};const seen=new Set();const jobs=[];for(const a of document.querySelectorAll('a[href*="-jid-"]')){const title=a.innerText.trim().split('\\n')[0];if(!title||seen.has(a.href))continue;seen.add(a.href);let c=a;for(let i=0;i<7&&c.parentElement&&c.parentElement.tagName!=='BODY';i++){const parent=c.parentElement;const ids=new Set(Array.from(parent.querySelectorAll('a[href*="-jid-"]')).map(x=>x.href));if(ids.size>1||parent.innerText.length>3500)break;c=parent;}jobs.push({source:'naukrigulf',url:a.href,title,card:c.innerText.slice(0,2000)});}const next=Array.from(document.querySelectorAll('a')).find(a=>a.innerText.trim()==='Next'&&a.getBoundingClientRect().height>0);return {challenge:false,jobs,next:next?.href||null};})()''')
        if data['challenge']:
            raise RuntimeError('Naukrigulf requires manual security verification')
        yield data['jobs']
        candidate = data['next']
        if candidate and candidate.startswith('https://www.naukrigulf.com/') and '-jobs-in-uae' in candidate:
            url = candidate
        else:
            url = None


def run(check=False, execute=False, terms=None, source='naukrigulf', track='devops_uae'):
    if source not in ('naukrigulf', 'linkedin', 'bayt', 'gulftalent', 'indeed'):
        raise ValueError('Unsupported verified application adapter')
    if track not in ('devops_uae', 'hosting_remote') or track == 'hosting_remote' and source != 'linkedin':
        raise ValueError('Remote hosting requires the adapter with an application-specific CV upload')
    if source == 'linkedin':
        from linkedin_adapter import inspect_job, already_applied, submit, search_pages
    elif source == 'naukrigulf':
        from naukri_adapter import inspect_job, already_applied, submit
        search_pages = globals()['search_pages']
    else:
        import board_adapter
        inspect_job = partial(board_adapter.inspect_job, source=source)
        search_pages = partial(board_adapter.search_pages, source=source)
        already_applied = board_adapter.already_applied
        submit = board_adapter.submit
    os.umask(0o077)
    error = profile_ready_error()
    if error:
        raise RuntimeError(error)
    if os.environ.get('JOB_SCREENING_MODE','local') == 'codex':
        from gpt_gateway import readiness_error
        error = readiness_error()
        if error:
            raise RuntimeError(error)
    config = json.loads((DATA / 'user_config.json').read_text())
    if not (config['personals'].get('email') or config['personals'].get('email_address')):
        # This is the owner-reviewed CV header, never text taken from a job.
        header = re.split(r'Professional Summary', config['questions']['user_information_all'], maxsplit=1, flags=re.I)[0]
        email = re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', header)
        if email: config['personals']['email_address'] = email[0]
    resume = DATA / 'resume.pdf'
    if track == 'hosting_remote':
        profile = json.loads((DATA / 'hosting-profile.json').read_text())
        resume = DATA / 'resumes/Karem_Elbostany_Hosting_Support_CV.pdf'
        if hashlib.sha256(resume.read_bytes()).hexdigest() != profile['cv_sha256']:
            raise RuntimeError('Remote hosting CV and professional facts do not match')
        config['questions']['user_information_all'] = profile['professional_text']
    digest = hashlib.sha256(resume.read_bytes()).hexdigest()
    journal = Journal(DATA / 'job-applications.sqlite3')
    store = Store(DATA / 'job-discovery.sqlite3')
    state = {'engine': source, 'track': track, 'running': True, 'started_at': int(time.time()), 'pid': os.getpid(), 'confirmed': 0, 'inspected': 0, 'skipped': 0, 'needs_input': 0, 'uncertain': 0}
    state_write(state)
    lock = open(DATA / '.application-adapter.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    host = {'naukrigulf': 'www.naukrigulf.com', 'linkedin': 'www.linkedin.com', 'bayt': 'www.bayt.com', 'gulftalent': 'www.gulftalent.com', 'indeed': 'ae.indeed.com'}[source]
    page = BrowserPage(host)
    state['run_id'] = os.environ.get('JOB_RUN_ID') or uuid.uuid4().hex
    journal.start_run(state['run_id'], source, os.environ.get('JOB_SCREENING_MODE', 'local'))
    state_write(state)
    try:
        if source == 'naukrigulf':
            page.goto('https://www.naukrigulf.com/mnj/userProfile/myHome')
            page.wait("/Welcome Back|LOGIN|Sign In/i.test(document.body.innerText)", 20)
            if not page.js("document.body.innerText.includes('Welcome Back!')"):
                raise RuntimeError('Sign in to Naukrigulf in the private browser first')
        elif source == 'linkedin':
            page.goto('https://www.linkedin.com/feed/')
            page.wait("location.pathname.startsWith('/feed')||/login|checkpoint|authwall/.test(location.pathname)", 25)
            if not page.read("location.pathname.startsWith('/feed')"):
                raise RuntimeError('Sign in to LinkedIn in the private browser first')
        else:
            from board_adapter import PROFILE
            page.goto(PROFILE[source])
            profile_selector = {'bayt': '[id^="updateCV-"]', 'gulftalent': 'form[name="uploadCV"]', 'indeed': 'button[aria-label="Open resume options"]'}[source]
            if not page.wait('!!document.querySelector(' + json.dumps(profile_selector) + ')', 45):
                raise RuntimeError('Sign in to ' + source + ' or complete its manual security verification')
        if check:
            if os.environ.get('JOB_SCREENING_MODE','local') == 'openai':
                from openai_screening import configuration_error
                error = configuration_error()
                if error:
                    raise RuntimeError(error)
            state.update(ready=True, stop_reason='Signed-in browser and approved CV verified; no applications started.')
            return state
        if os.environ.get('JOB_SCREENING_MODE','local')=='groq' and (not os.environ.get('GROQ_API_KEY') or os.environ.get('JOB_AI_PROVIDER') != 'groq' or os.environ.get('JOB_SCREENING_SHARING_APPROVED')!='1'):
            raise RuntimeError('The configured free-plan screening provider is missing')
        known = journal.known_urls(os.environ.get('JOB_SCREENING_MODE', 'local'), digest)
        seen = set()
        selected_terms = ['Linux Hosting Support', 'cPanel Support', 'Linux Support Engineer', 'WordPress Technical Support'] if track == 'hosting_remote' else TERMS
        for term in terms or selected_terms:
            # Finish collecting a query before navigating away to its listings.
            candidates = []
            pages = search_pages(page, term, remote=True) if track == 'hosting_remote' else search_pages(page, term)
            for jobs in pages:
                candidates.extend(jobs)
            records = []
            for candidate in candidates:
                url = canonical_url(source, candidate['url'])
                if not url or url in seen:
                    continue
                seen.add(url)
                card = candidate['card']
                location = next((line.strip() for line in card.splitlines() if 'United Arab Emirates' in line), '')
                records.append({'source': source, 'url': url, 'title': candidate['title'], 'company': '', 'location': location,
                                'location_verified': is_uae(location), 'application_status': 'not_applied', 'platform_applied':bool(re.search(r'^Applied$', card, re.M))})
            store.save({'source': source, 'term': term, 'status': 'ok' if records else 'unrecognized', 'checked_at': int(time.time()),
                        'search_url': search_url(source, term), 'message': f'{len(records)} authenticated listings collected. Applications tracked separately.', 'jobs': records})
            for candidate in records:
                role = re.compile(r'linux|hosting|cpanel|wordpress|technical support|systems? admin', re.I) if track == 'hosting_remote' else ROLE
                if candidate['url'] in known or not role.search(candidate['title']) or OUTSIDE_ROLE.search(candidate['title']):
                    continue
                if candidate.get('platform_applied'):
                    journal.review(candidate, digest, False, 'Already applied on the platform; no repeat submission')
                    state['skipped'] += 1; state_write(state); continue
                try:
                    job = inspect_job(page, candidate['url'])
                except RuntimeError as error:
                    if 'no application attempted' not in str(error).lower() and 'job layout unavailable' not in str(error).lower():
                        raise
                    journal.review(candidate, digest, False, 'Listing details could not be established; no application attempted.')
                    state['skipped'] += 1
                    state_write(state)
                    continue
                job['track'] = track
                state['inspected'] += 1
                if already_applied(job):
                    journal.review(job, digest, False, 'Already applied on the platform; no repeat submission')
                    state['skipped'] += 1
                    state_write(state)
                    continue
                if not job['easyApply']:
                    journal.review(job, digest, False, 'External or unsupported application flow; not submitted automatically')
                    state['skipped'] += 1
                    state_write(state)
                    continue
                if track == 'devops_uae' and not is_uae(job['location']):
                    journal.review(job, digest, False, 'UAE job location could not be established')
                    state['skipped'] += 1
                    state_write(state)
                    continue
                decision = screen(config, {k: job[k] for k in ('title', 'company', 'head', 'description')}, scope=track)
                job['screening'] = dict(decision, provider=os.environ.get('JOB_SCREENING_MODE', 'local'))
                reason = decision['reason'] + (' Gaps: ' + '; '.join(decision['gaps']) if decision['gaps'] else '')
                journal.review(job, digest, decision['eligible'], reason)
                known.add(job['url'])
                if not decision['eligible']:
                    state['skipped'] += 1
                elif execute:
                    # Recheck approval and CV identity immediately before the submit action.
                    if profile_ready_error() or hashlib.sha256(resume.read_bytes()).hexdigest() != digest:
                        raise RuntimeError('Application profile changed during the run')
                    outcome = submit(page, job, journal, digest) if source == 'naukrigulf' else submit(page, job, journal, digest, config, resume)
                    if outcome in state:
                        state[outcome] += 1
                    print('Application outcome: ' + json.dumps({'title': job['title'], 'company': job['company'], 'status': outcome}), flush=True)
                    if outcome == 'uncertain':
                        state['stop_reason'] = 'Source paused after an uncertain platform response; the attempted job will not be retried.'
                        state_write(state)
                        return state
                state_write(state)
        state['stop_reason'] = 'Available search results reviewed; only confirmed submissions counted.' if execute else 'Review-only cycle completed; no applications sent.'
        return state
    finally:
        error = sys.exc_info()[1]
        attention = error and any(term in str(error).lower() for term in ('manual security', 'sign in to naukrigulf', 'sign in to linkedin', 'connect chatgpt', 'gpt fit checks'))
        journal.finish_run(state['run_id'], 'attention_required' if attention else 'failed' if error else 'completed',
                           {key: state.get(key, 0) for key in ('confirmed', 'inspected', 'skipped', 'needs_input', 'uncertain')},
                           str(error) if error else state.get('stop_reason', 'Cycle completed'))
        state.update(running=False, finished_at=int(time.time()))
        state_write(state)
        page.close()
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--term', action='append')
    parser.add_argument('--source', choices=('naukrigulf', 'linkedin', 'bayt', 'gulftalent', 'indeed'), default='naukrigulf')
    parser.add_argument('--track', choices=('devops_uae', 'hosting_remote'), default='devops_uae')
    args = parser.parse_args()
    try:
        result = run(args.check, args.execute, args.term, args.source, args.track)
        print(json.dumps(result), flush=True)
    except Exception as error:
        try:
            old = json.loads(STATE.read_text())
        except (OSError, ValueError):
            old = {}
        attention=('manual security verification' in str(error).lower() or 'sign in to naukrigulf' in str(error).lower() or 'sign in to linkedin' in str(error).lower() or getattr(error,'status_code',None)==429)
        old.update(running=False, exit_code=0 if attention else 1, attention_required=attention, stop_reason=str(error)[:400], finished_at=int(time.time()))
        state_write(old)
        print('Application cycle stopped: ' + str(error)[:400], file=sys.stderr, flush=True)
        sys.exit(0 if attention else 1)
