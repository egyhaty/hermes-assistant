"""Conservative first-party apply flows for Bayt, GulfTalent and Indeed."""
import re
import time
from urllib.parse import urlsplit

from job_sources import canonical_url, search_url

DOMAINS = {'bayt': 'bayt.com', 'gulftalent': 'gulftalent.com', 'indeed': 'indeed.com'}
PROFILE = {'bayt': 'https://www.bayt.com/en/mycvs/', 'gulftalent': 'https://www.gulftalent.com/candidates/edit-cv', 'indeed': 'https://profile.indeed.com/'}
HOSTS = {'bayt': 'www.bayt.com', 'gulftalent': 'www.gulftalent.com', 'indeed': 'ae.indeed.com'}


def first_party_application(source, url):
    p = urlsplit(url)
    return p.scheme == 'https' and not p.username and not p.password and p.port in (None, 443) and (p.hostname == DOMAINS[source] or (p.hostname or '').endswith('.' + DOMAINS[source]))


def search_pages(page, term, source):
    page.goto(search_url(source, term))
    page.wait("document.querySelector('main,article,[role=main]')||/Just a moment|Verify you are human/i.test(document.title+' '+document.body.innerText.slice(0,500))", 30)
    data = page.js('''(()=>{const text=document.body.innerText;return {challenge:/Just a moment|Verify you are human|security verification/i.test(document.title+' '+text.slice(0,1000)),links:Array.from(document.querySelectorAll('a[href]')).map(a=>{let p=a.closest('article,li,[data-job-id]')||a.parentElement;return {url:a.href,title:a.querySelector('[title]')?.getAttribute('title')||a.getAttribute('aria-label')||a.innerText.trim().split('\\n').find(x=>!/^new$/i.test(x.trim()))||'',card:p.innerText.slice(0,1800)}})}})()''')
    if data['challenge']: raise RuntimeError(source + ' requires manual security verification')
    found = {}
    for item in data['links']:
        url = canonical_url(source, item['url'])
        if url and item['title']: found[url] = dict(item, source=source, url=url)
    yield list(found.values())


def inspect_job(page, url, source):
    url = canonical_url(source, url)
    if not url: raise ValueError('Not a supported job URL')
    page.goto(url)
    page.wait("document.querySelector('h1,[data-testid=jobsearch-JobInfoHeader-title]')||/Just a moment|security verification/i.test(document.title+' '+document.body.innerText.slice(0,500))", 30)
    data = page.js('''(()=>{const s=document.body.innerText;let structured=null;for(const e of document.querySelectorAll('script[type="application/ld+json"]')){try{const walk=x=>{if(Array.isArray(x)){for(const y of x)walk(y)}else if(x&&typeof x==='object'){if([].concat(x['@type']||[]).includes('JobPosting'))structured=x;for(const k of ['@graph','itemListElement','item'])if(x[k])walk(x[k])}};walk(JSON.parse(e.textContent))}catch{}}const clean=html=>{const e=document.createElement('div');e.innerHTML=html||'';return e.innerText||e.textContent};const title=structured?.title||document.querySelector('[data-testid="jobsearch-JobInfoHeader-title"],main h1,h1')?.innerText.trim()||'';const at=s.indexOf(title);let begin=-1;for(const marker of ['Full job description','Job description / Role','Job Description','Job description']){const i=s.indexOf(marker,Math.max(0,at));if(i>=0&&(begin<0||i<begin))begin=i}let locations=[].concat(structured?.jobLocation||[]).map(x=>{const a=x.address||{};return [a.addressLocality,a.addressRegion,typeof a.addressCountry==='string'?a.addressCountry:a.addressCountry?.name].filter(Boolean).join(', ')}).join('; ');const head=at>=0?s.slice(at,at+2000):'';const controls=Array.from(document.querySelectorAll('button,a,[role=button]')).filter(e=>e.getBoundingClientRect().height>0);return {url:location.href,title,company:structured?.hiringOrganization?.name||'',head,location:locations||head,description:structured?.description?clean(structured.description):begin>=0?s.slice(begin,begin+18000):'',easyApply:controls.some(e=>/^(?:Apply|Apply now|Easy apply)$/i.test(e.innerText.trim())&&!e.disabled&&(!e.href||(()=>{const u=new URL(e.href),h=u.hostname,d=location.hostname.split('.').slice(-2).join('.');return u.protocol==='https:'&&!u.username&&!u.password&&(!u.port||u.port==='443')&&(h===d||h.endsWith('.'+d))})())),alreadyApplied:controls.some(e=>/^Already applied$|^Applied$/i.test(e.innerText.trim()))||/You (?:have )?(?:already )?applied (?:to|for) this (?:job|role|position)/i.test(head),challenge:/Just a moment|Verify you are human|security verification/i.test(document.title+' '+s.slice(0,700))}})()''')
    if data['challenge']: raise RuntimeError(source + ' requires manual security verification')
    if canonical_url(source, data['url']) != url or not data['title'] or not data['description'] or not data['company']:
        raise RuntimeError(source + ' job layout unavailable; no application attempted')
    data.update(source=source, url=url)
    return data


def already_applied(job):
    return bool(job.get('alreadyApplied'))


def submit(page, job, journal, digest, config, resume):
    from browser_application_form import complete_form
    from multisite_worker import cv_sync_error
    source = job['source']
    error = cv_sync_error(source)
    if error: raise RuntimeError(error)
    if already_applied(job) or not job.get('easyApply'): return 'unsupported'
    from application_context import require_reviewed_page
    require_reviewed_page(page, job)
    if not journal.claim(job['url'], digest): return 'not_claimed'
    try:
        page.js('''(()=>{const b=Array.from(document.querySelectorAll('button,a,[role=button]')).find(e=>e.getBoundingClientRect().height>0&&!e.disabled&&/^(?:Apply|Apply now|Easy apply)$/i.test(e.innerText.trim())&&(!e.href||(()=>{const u=new URL(e.href),h=u.hostname,d=location.hostname.split('.').slice(-2).join('.');return u.protocol==='https:'&&!u.username&&!u.password&&(!u.port||u.port==='443')&&(h===d||h.endsWith('.'+d))})()));if(!b)throw Error('First-party Apply missing');b.click();return true})()''')
        time.sleep(3)
        if not first_party_application(source, page.js('location.href')):
            journal.finish(job['url'], 'needs_input', 'External application flow opened; no further answers or Submit were sent.')
            return 'needs_input'
        result = complete_form(page, config, resume, digest, allow_profile_cv=True)
        if result['status'] == 'needs_input':
            journal.finish(job['url'], 'needs_input', result['reason'])
            return 'needs_input'
        if result['status'] == 'sent':
            check = inspect_job(page, job['url'], source)
            if already_applied(check):
                from application_proof import capture
                proof = capture(page, job['url'])
                if proof: journal.attach_proof(job['url'], proof)
                journal.finish(job['url'], 'confirmed', 'The platform acknowledged sending and Applied persisted on the original listing.', result['evidence'] + '\n' + check['head'][:700])
                return 'confirmed'
        journal.finish(job['url'], 'uncertain', 'No durable first-party confirmation; automatic retry disabled.')
        return 'uncertain'
    except Exception as error:
        journal.finish(job['url'], 'uncertain', 'Application attempt stopped: ' + type(error).__name__)
        raise
