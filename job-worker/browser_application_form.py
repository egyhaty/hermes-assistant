"""Bounded normal form navigation with verified contact answers and the selected local CV."""
import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path

from application_answers import answer_for, is_resume_field
from worker_guard import profile_ready_error

DATA = Path(os.environ.get('JOB_DATA', '/data'))


SNAPSHOT = r'''(()=>{const visible=e=>e.getBoundingClientRect().height>0;const dialog=Array.from(document.querySelectorAll('[role=dialog]')).find(visible)||Array.from(document.querySelectorAll('main form,form[name*=apply],form[id*=apply]')).find(e=>visible(e)&&Array.from(e.querySelectorAll('button')).some(b=>/^(?:Submit application|Send application|Next|Continue|Review|Apply now|Apply)$/i.test(b.innerText.trim())));if(!dialog)return {missing:true,text:document.body.innerText.slice(-1000),fields:[],buttons:[]};for(const e of document.querySelectorAll('[data-hermes-application]'))e.removeAttribute('data-hermes-application');for(const e of document.querySelectorAll('[data-hermes-field]'))e.removeAttribute('data-hermes-field');dialog.setAttribute('data-hermes-application','true');const fields=[];let i=0;for(const e of dialog.querySelectorAll('input,textarea,select')){if(e.type==='hidden'||e.type!=='file'&&!visible(e))continue;const id='field-'+i++;e.setAttribute('data-hermes-field',id);const direct=Array.from(e.labels||[]).map(x=>x.innerText).join(' ').trim();const label=e.getAttribute('aria-label')||direct||e.placeholder||'';let question=['radio','checkbox'].includes(e.type)?(e.closest('fieldset')?.querySelector('legend')?.innerText||e.closest('[data-test-form-element]')?.querySelector('label')?.innerText||label):label;fields.push({id,originalId:e.id,name:e.name,type:e.type||e.tagName.toLowerCase(),label,question,required:!!e.required||e.getAttribute('aria-required')==='true'||e.closest('fieldset')?.getAttribute('aria-required')==='true',value:e.type==='file'?'':e.value,checked:e.checked,options:e.tagName==='SELECT'?Array.from(e.options).map(o=>({value:o.value,label:o.text})):[]})}const buttons=Array.from(dialog.querySelectorAll('button')).filter(visible).map(e=>({label:(e.innerText||e.getAttribute('aria-label')||'').trim(),disabled:e.disabled}));const errors=Array.from(dialog.querySelectorAll('[role=alert],.artdeco-inline-feedback--error,[aria-invalid=true]')).filter(visible).map(e=>e.innerText||e.getAttribute('aria-label')||'Invalid field');return {missing:false,text:dialog.innerText,fields,buttons,errors}})()'''


def _selector(field):
    return '[data-hermes-application=true] [data-hermes-field=' + json.dumps(field['id']) + ']'


def _fill(page, field, value):
    selector = _selector(field)
    # Normal native controls and change events; no private submission endpoints.
    code = '''(()=>{const e=document.querySelector(SEL);if(!e)throw Error('Form changed');const value=VALUE;
    if(e.tagName==='SELECT'){const o=Array.from(e.options).find(o=>o.value.toLowerCase()===value.toLowerCase()||o.text.trim().toLowerCase()===value.toLowerCase()||(value==='+971'&&o.text.includes('+971')));if(!o)return false;e.value=o.value}
    else {const proto=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(e,value)}
    e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return true})()'''.replace('SEL', json.dumps(selector)).replace('VALUE', json.dumps(value))
    return page.js(code)


def _click(page, label):
    return page.js('''(()=>{const d=document.querySelector('[data-hermes-application=true]');const b=Array.from(d.querySelectorAll('button')).find(e=>e.getBoundingClientRect().height>0&&!e.disabled&&(e.innerText||e.getAttribute('aria-label')||'').trim()===LABEL);if(!b)throw Error('Form button changed');b.click();return true})()'''.replace('LABEL', json.dumps(label)))


def complete_form(page, config, resume, digest, allow_profile_cv=False):
    """Never completes unknown questions or counts a click as a confirmed submission."""
    resume = Path(resume)
    allowed = {DATA / 'resume.pdf', DATA / 'resumes/Karem_Elbostany_Hosting_Support_CV.pdf'}
    if resume not in allowed or resume.is_symlink() or not resume.is_file() or not resume.read_bytes().startswith(b'%PDF-') or hashlib.sha256(resume.read_bytes()).hexdigest() != digest:
        raise ValueError('Selected verified resume is unavailable')
    aliases = DATA / 'application-resumes'
    aliases.mkdir(exist_ok=True, mode=0o700)
    selected = aliases / ('Karem_' + ('Hosting_' if 'Hosting' in resume.name else 'DevOps_') + digest[:12] + '.pdf')
    shutil.copyfile(resume, selected)
    selected.chmod(0o600)
    if allow_profile_cv and resume != DATA / 'resume.pdf':
        raise ValueError('A hosting CV requires an application-specific upload')
    uploaded = bool(allow_profile_cv)
    signatures = set()
    for step in range(10):
        page.wait("document.querySelector('[role=dialog]')||/application (?:was |has been )?(?:successfully )?(?:sent|submitted|received)|successfully applied|thank you for applying/i.test(document.body.innerText)", 20)
        state = page.js(SNAPSHOT)
        if re.search(r'application (?:was |has been )?(?:successfully )?(?:sent|submitted|received)|successfully applied|thank you for applying', state['text'], re.I):
            return {'status': 'sent', 'evidence': state['text'][:1000]}
        if state['missing']:
            return {'status': 'uncertain', 'reason': 'Application form disappeared without a confirmation'}
        signature = (tuple((x['question'], x['type']) for x in state['fields']), tuple(x['label'] for x in state['buttons']))
        if signature in signatures:
            return {'status': 'needs_input', 'reason': 'The application did not advance; its validation needs review'}
        signatures.add(signature)
        unknown = []
        has_dial_code = any(re.search(r'country.*code|dial(?:ing)? code', x['label'], re.I) for x in state['fields'])
        for field in state['fields']:
            if field['type'] == 'file':
                if not is_resume_field(field):
                    if field['required']: unknown.append(field['question'] or 'Required attachment type is unknown')
                    continue
                selector = _selector(field)
                dom = page.call('DOM.getDocument')['root']['nodeId']
                node = page.call('DOM.querySelector', nodeId=dom, selector=selector)['nodeId']
                if not node: raise RuntimeError('Resume input changed')
                page.call('DOM.setFileInputFiles', nodeId=node, files=[str(selected)])
                uploaded = page.wait('document.querySelector("[data-hermes-application=true]").innerText.includes(' + json.dumps(selected.name) + ')', 25)
                if not uploaded:
                    return {'status': 'needs_input', 'reason': 'No final Submit clicked; the platform did not acknowledge the selected CV upload'}
                continue
            if field['type'] in ('checkbox', 'radio'):
                if field['type'] == 'checkbox' and re.search(r'^follow\b|subscribe|job alerts', field['label'], re.I):
                    if field['checked']:
                        page.js('document.querySelector(' + json.dumps(_selector(field)) + ').click()')
                    continue
                # A cached selection is not an owner-verified qualification.
                # Resume selection is handled by the current-CV checks below.
                if field.get('checked') and not (is_resume_field(field) and (allow_profile_cv or selected.name in field['label'])):
                    unknown.append(field['question'] or 'Unverified prefilled selection')
                    continue
                # Custom question groups and attestation/consent controls need an explicit parser.
                if field['required']:
                    unknown.append(field['question'] or 'Required selection')
                continue
            value = answer_for(field['question'], config)
            if value is None:
                if field['required'] or field['value']:
                    unknown.append(field['question'] or 'Unlabelled field')
                continue
            if re.search(r'phone|mobile', field['label'], re.I):
                expected = re.sub(r'\D', '', value)
                current = re.sub(r'\D', '', field['value'])
                if current and current in (expected, expected.removeprefix('971')):
                    continue
                if has_dial_code and expected.startswith('971'): value = expected[3:]
            if not _fill(page, field, value): unknown.append(field['question'])
        if unknown:
            return {'status': 'needs_input', 'reason': 'No final Submit clicked; verified answers are missing for: ' + '; '.join(dict.fromkeys(unknown))[:700]}
        state = page.js(SNAPSHOT)
        if state.get('errors'):
            return {'status': 'needs_input', 'reason': 'No final Submit clicked; the platform reports a form validation error'}
        buttons = [b['label'] for b in state['buttons'] if not b['disabled']]
        final = next((label for label in buttons if re.fullmatch(r'Submit application|Send application', label, re.I)), None)
        if final:
            if not uploaded or not allow_profile_cv and selected.name not in state['text']:
                return {'status': 'needs_input', 'reason': 'No final Submit clicked; the selected CV could not be established in this application'}
            if profile_ready_error() or hashlib.sha256(resume.read_bytes()).hexdigest() != digest:
                raise RuntimeError('Application profile or selected CV changed before submission')
            _click(page, final)
            for _ in range(25):
                state = page.js(SNAPSHOT)
                if re.search(r'application (?:was |has been )?(?:successfully )?(?:sent|submitted|received)|successfully applied|thank you for applying', state['text'], re.I):
                    return {'status': 'sent', 'evidence': state['text'][:1000]}
                time.sleep(1)
            return {'status': 'uncertain', 'reason': 'No clear confirmation after the final Submit'}
        advance = next((label for label in buttons if re.fullmatch(r'Next|Continue|Review(?: your application)?', label, re.I)), None)
        if not advance:
            return {'status': 'needs_input', 'reason': 'No final Submit clicked; the next application step is unsupported'}
        _click(page, advance)
        time.sleep(2)
    return {'status': 'needs_input', 'reason': 'No final Submit clicked; too many application steps require review'}
