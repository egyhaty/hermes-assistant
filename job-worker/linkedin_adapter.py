"""LinkedIn listing extraction and conservative Easy Apply; never delegates form answers to GPT."""
import re
import time
from urllib.parse import urlencode

from job_sources import canonical_url


def search_pages(page, term, remote=False):
    params = {'keywords': term, 'f_AL': 'true', 'location': 'Worldwide' if remote else 'United Arab Emirates'}
    if remote: params['f_WT'] = '2'
    else: params['geoId'] = '104305776'
    visited = set()
    start = 0
    while True:
        page.goto('https://www.linkedin.com/jobs/search/?' + urlencode(dict(params, start=start)))
        page.wait("document.querySelector('[componentkey^=\"job-card-component-ref-\"],li[data-occludable-job-id],a[href*=\"/jobs/view/\"]')||/checkpoint|authwall|login/.test(location.pathname)", 30)
        if page.js("/checkpoint|authwall|login/.test(location.pathname)"):
            raise RuntimeError('Sign in to LinkedIn or complete its security check in the private browser')
        jobs = page.js('''(()=>{const result=[],seen=new Set();const add=(id,card,title)=>{if(!/^\\d+$/.test(id)||seen.has(id)||!title)return;seen.add(id);result.push({source:'linkedin',url:'https://www.linkedin.com/jobs/view/'+id+'/',title:title.trim(),card:card.innerText.slice(0,1800)})};for(const c of document.querySelectorAll('[componentkey^="job-card-component-ref-"]')){const id=c.getAttribute('componentkey').match(/(\\d+)$/)?.[1];add(id||'',c,c.querySelector('p span[aria-hidden=true]')?.innerText||c.querySelector('p')?.innerText||'')}for(const c of document.querySelectorAll('li[data-occludable-job-id]')){const a=c.querySelector('a[href*="/jobs/view/"]');add(c.getAttribute('data-occludable-job-id')||'',c,a?.querySelector('[aria-hidden=true]')?.innerText||a?.innerText.split('\\n')[0]||'')}return result})()''')
        signature = tuple(x['url'] for x in jobs)
        if not signature or signature in visited: return
        visited.add(signature)
        yield jobs
        start += len(jobs)
        if not page.js("Array.from(document.querySelectorAll('button,a')).some(e=>e.getBoundingClientRect().height>0&&!e.disabled&&/next/i.test(e.getAttribute('aria-label')||e.innerText)&&!/next job/i.test(e.getAttribute('aria-label')||''))"):
            return


def inspect_job(page, url):
    url = canonical_url('linkedin', url)
    if not url: raise ValueError('Not a LinkedIn job URL')
    page.goto(url)
    page.wait("/About the job|Job description/i.test(document.body.innerText)||/checkpoint|login|authwall/.test(location.pathname)", 30)
    data = page.js('''(()=>{const text=document.body.innerText;const meta=document.title.split(' | ');const metaTitle=meta.length>=3?meta[0].replace(/^\\(\\d+\\)\\s*/,'').trim():'';const title=document.querySelector('.job-details-jobs-unified-top-card__job-title h1,.jobs-unified-top-card__job-title h1,main h1,h1')?.innerText.trim()||metaTitle;const at=text.indexOf(title);let about=text.indexOf('About the job',at);if(about<0)about=text.indexOf('Job description',at);const head=at>=0?text.slice(at,about>at?Math.min(about,at+1800):at+1800):'';const company=document.querySelector('.job-details-jobs-unified-top-card__company-name,.jobs-unified-top-card__company-name,main a[href*="/company/"]')?.innerText.trim()||(meta.length>=3?meta[1].trim():'');const buttons=Array.from(document.querySelectorAll('button,[role=button]')).filter(e=>e.getBoundingClientRect().height>0);return {url:location.origin+location.pathname,title,company,head,location:head,description:about>=0?text.slice(about,(()=>{const ends=['Set alert for similar jobs','Put your best foot forward','See how you compare','About the company'].map(x=>text.indexOf(x,about+15)).filter(x=>x>about);return ends.length?Math.min(...ends):text.length})()):'',easyApply:buttons.some(e=>/^(?:LinkedIn\\s+)?Easy Apply$/i.test(e.innerText.trim())&&!e.disabled),alreadyApplied:buttons.some(e=>/^Applied$/i.test(e.innerText.trim()))||/You applied (?:to this job|on )|Application status[\\s\\S]{0,120}Application submitted/i.test(head),challenge:/checkpoint|login|authwall/.test(location.pathname)}})()''')
    if data['challenge']: raise RuntimeError('Sign in to LinkedIn or complete its security check in the private browser')
    if canonical_url('linkedin', data['url']) != url or not data['title'] or not data['description'] or not data['company']:
        raise RuntimeError('LinkedIn job details are unavailable; no application attempted')
    data.update(source='linkedin', url=url)
    return data


def already_applied(job):
    return bool(job.get('alreadyApplied'))


def submit(page, job, journal, digest, config, resume):
    from browser_application_form import complete_form
    if already_applied(job) or not job.get('easyApply'):
        return 'already_applied' if already_applied(job) else 'unsupported'
    from application_context import require_reviewed_page
    require_reviewed_page(page, job)
    if not journal.claim(job['url'], digest): return 'not_claimed'
    try:
        page.js('''(()=>{const b=Array.from(document.querySelectorAll('button,[role=button]')).find(e=>e.getBoundingClientRect().height>0&&/^(?:LinkedIn\\s+)?Easy Apply$/i.test(e.innerText.trim())&&!e.disabled);if(!b)throw Error('Easy Apply missing');b.click();return true})()''')
        result = complete_form(page, config, resume, digest)
        if result['status'] == 'needs_input':
            journal.finish(job['url'], 'needs_input', result['reason'])
            return 'needs_input'
        if result['status'] == 'sent':
            # A modal success message alone is insufficient; reload the same job.
            check = inspect_job(page, job['url'])
            if already_applied(check):
                from application_proof import capture
                proof = capture(page, job['url'])
                if proof: journal.attach_proof(job['url'], proof)
                journal.finish(job['url'], 'confirmed', 'LinkedIn acknowledged sending and Applied persisted on the original listing.', result['evidence'] + '\n' + check['head'][:700])
                return 'confirmed'
        journal.finish(job['url'], 'uncertain', 'LinkedIn did not provide durable confirmation; automatic retry disabled.')
        return 'uncertain'
    except Exception as error:
        journal.finish(job['url'], 'uncertain', 'LinkedIn attempt stopped: ' + type(error).__name__)
        raise
