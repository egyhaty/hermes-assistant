"""Verified Naukrigulf Easy Apply flow. Unknown forms stop; only platform evidence confirms success."""
import re
import time

from job_sources import canonical_url

SUCCESS = re.compile(r'You have successfully applied to', re.I)


def inspect_job(page, url):
    url = canonical_url('naukrigulf', url)
    if not url:
        raise ValueError('Not a Naukrigulf job URL')
    page.goto(url)
    page.wait("document.body.innerText.includes('Job Description')||document.body.innerText.includes('security verification')", 20)
    data = page.js('''(()=>{const text=document.body.innerText;const title=document.querySelector('h1')?.innerText.trim()||'';const lines=text.split('\\n').map(x=>x.trim()).filter(Boolean);const at=lines.indexOf(title);const start=text.indexOf('Job Description');let end=text.indexOf('Employment Type',start);if(end<0)end=text.indexOf('Company Industry',start);if(end<0)end=text.indexOf('Disclaimer:',start);const loc=text.indexOf('Job Location');const edu=text.indexOf('Education',loc);return {url:location.origin+location.pathname,title,company:at>=0?lines[at+1]:'',location:loc>=0?text.slice(loc+12,edu>loc?edu:loc+180).trim():'',head:text.slice(0,1500),description:start>=0?text.slice(start,end>start?end:start+10000):'',easyApply:Array.from(document.querySelectorAll('button')).some(x=>x.innerText.trim()==='Easy Apply'&&!x.disabled),challenge:/security verification|verify you are not a bot|Just a moment/i.test(text.slice(0,1200))};})()''')
    if data['challenge']:
        raise RuntimeError('Naukrigulf requires manual security verification')
    # Some templates wrap the title and company in one multiline h1.
    title_lines = [line.strip() for line in data['title'].splitlines() if line.strip()]
    if len(title_lines) > 1:
        data['title'] = title_lines[0]
        data['company'] = data['company'] or title_lines[1]
    if canonical_url('naukrigulf', data['url']) != url:
        raise RuntimeError('The browser left the reviewed job URL')
    if not data['title'] or not data['description']:
        raise RuntimeError('Job layout unavailable; no application attempted')
    data['source'] = 'naukrigulf'
    data['url'] = url
    return data


def already_applied(job):
    return 'Already Applied' in job['head']


def submit(page, job, journal, digest):
    url = job['url']
    if already_applied(job) or not job['easyApply']:
        return 'already_applied' if already_applied(job) else 'unsupported'
    if not journal.claim(url, digest):
        return 'not_claimed'
    try:
        page.js('''(()=>{const b=Array.from(document.querySelectorAll('button')).find(x=>x.innerText.trim()==='Easy Apply'&&!x.disabled);if(!b)throw Error('No enabled Easy Apply control');b.click();return true;})()''')
        result = None
        for _ in range(25):
            result = page.js('''({head:document.body.innerText.slice(0,1500),fields:Array.from(document.querySelectorAll('input,textarea,select')).filter(x=>x.type!=='hidden'&&x.getBoundingClientRect().height>0).map(x=>({name:x.name,label:x.getAttribute('aria-label')||x.placeholder||'',required:x.required})),buttons:Array.from(document.querySelectorAll('button')).filter(x=>x.getBoundingClientRect().height>0).map(x=>x.innerText.trim())})''')
            if SUCCESS.search(result['head']) or 'Already Applied' in result['head']:
                # Reload the original listing to establish durable platform state.
                check = inspect_job(page, url)
                if already_applied(check):
                    from application_proof import capture
                    proof = capture(page, url)
                    if proof: journal.attach_proof(url, proof)
                    journal.finish(url, 'confirmed', 'Success was acknowledged and Already Applied persisted on the original listing.', result['head'][:650] + '\n' + check['head'][:650])
                    return 'confirmed'
                break
            if result['fields'] and any(re.search(r'submit|continue|apply', b, re.I) for b in result['buttons']):
                journal.finish(url, 'needs_input', 'A further form requires review; no answers were entered and no additional Submit was clicked.', str(result['fields'])[:1500])
                return 'needs_input'
            time.sleep(1)
        journal.finish(url, 'uncertain', 'No durable platform confirmation; automatic retry disabled.', str(result or {})[:1500])
        return 'uncertain'
    except Exception as error:
        try:
            journal.finish(url, 'uncertain', 'Stopped after an attempted application: ' + type(error).__name__)
        except ValueError:
            pass
        raise
