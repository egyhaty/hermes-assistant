"""Job-specific CVs assembled only from the owner's editable, reviewed facts.

Job descriptions influence ordering, never generate claims or employer attribution.
Private source files and artifacts belong in JOB_DATA, never in this repository.
"""
import copy
import hashlib
import json
import os
import re
from pathlib import Path
from xml.sax.saxutils import escape

VERSION = 1

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tokens(text):
    return set(re.findall(r'[a-z][a-z0-9+#.-]{2,}', text.lower()))


def tailor(source, job):
    result = copy.deepcopy(source)
    terms = tokens(str(job.get('title', '')) + ' ' + str(job.get('description', '')))
    def score(text): return len(tokens(text) & terms)
    def ranked(values): return sorted(values, key=score, reverse=True)
    # Every sentence remains verbatim from the reviewed source. Keep ALL bullets
    # and all context/qualifiers, especially project-vs-employer distinctions.
    result['summary'] = result['summary'][:1] + ranked(result['summary'][1:])
    result['skills'] = ranked(result['skills'])
    for role in result['experience'][:2]:
        role['bullets'] = ranked(role['bullets'])
    result['projects'] = sorted(result['projects'], key=lambda x: score(x['title'] + ' ' + ' '.join(x['bullets'])), reverse=True)
    return result


def render(source, destination):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether
    styles = {
        'name': ParagraphStyle('name', fontName='Helvetica-Bold', fontSize=23, leading=27, spaceAfter=6),
        'heading': ParagraphStyle('heading', fontName='Helvetica-Bold', fontSize=11, leading=14, spaceBefore=10, spaceAfter=5, textColor=colors.HexColor('#172b43'), keepWithNext=True),
        'role': ParagraphStyle('role', fontName='Helvetica-Bold', fontSize=10, leading=13, spaceBefore=7, spaceAfter=3, keepWithNext=True),
        'body': ParagraphStyle('body', fontName='Helvetica', fontSize=9.3, leading=12.5, spaceAfter=4),
        'bullet': ParagraphStyle('bullet', fontName='Helvetica', fontSize=9.3, leading=12.5, leftIndent=8, firstLineIndent=-8, spaceAfter=3),
    }
    story = []
    def text(value, kind='body'): story.append(Paragraph(escape(value), styles[kind]))
    text(source['name'], 'name'); text(source['headline'], 'role')
    for line in source['contact']: text(line)
    text('PROFESSIONAL SUMMARY', 'heading'); text(' '.join(source['summary']))
    text('TECHNICAL SKILLS', 'heading')
    for line in source['skills']: text(line)
    text('PROFESSIONAL EXPERIENCE', 'heading')
    for role in source['experience'][:2]:
        text(role['title'], 'role'); text(' | '.join(x for x in (role['company'], role['dates'], role.get('note', '')) if x))
        for bullet in role['bullets']: text('- ' + bullet, 'bullet')
    story.append(PageBreak())
    text('PROFESSIONAL EXPERIENCE CONTINUED', 'heading')
    for role in source['experience'][2:]:
        text(role['title'] + ' | ' + role['company'], 'role'); text(role['dates'])
        for bullet in role['bullets']: text('- ' + bullet, 'bullet')
    text('EARLIER EXPERIENCE', 'heading')
    for line in source['earlier']: text(line)
    text('INDEPENDENT DEVOPS AND CLOUD PROJECTS', 'heading')
    for project in source['projects']:
        text(project['title'], 'role')
        for bullet in project['bullets']: text('- ' + bullet, 'bullet')
    text('CERTIFICATION AND EDUCATION', 'heading')
    for line in source['education']: text(line)
    def footer(canvas, doc):
        canvas.setFont('Helvetica', 8); canvas.drawRightString(A4[0]-43, 22, str(doc.page))
    SimpleDocTemplate(str(destination), pagesize=A4, leftMargin=43, rightMargin=43, topMargin=35, bottomMargin=35,
                      title=source['name']+' - Infrastructure CV', author=source['name']).build(story, onFirstPage=footer, onLaterPages=footer)
    Path(destination).chmod(0o600)


def prepare(data, job, baseline, track='devops_uae'):
    data, baseline = Path(data), Path(baseline)
    source_path = data / 'cv-source' / (track + '.json')
    if not source_path.is_file() or source_path.is_symlink():
        raise ValueError('Editable reviewed CV source is unavailable')
    source = json.loads(source_path.read_text())
    base_digest = sha(baseline)
    if source.get('baseline_sha256') != base_digest:
        raise ValueError('Editable CV source and reviewed baseline differ')
    tailored = tailor(source, job)
    key = hashlib.sha256(json.dumps({'version': VERSION, 'source': source, 'job_url': job['url'],
                                     'title': job.get('title'), 'description': job.get('description')}, sort_keys=True).encode()).hexdigest()
    root = data / 'tailored-resumes' / key
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    pdf = root / 'resume.pdf'
    if not pdf.exists(): render(tailored, pdf)
    metadata = {'version': VERSION, 'job_url': job['url'], 'company': job.get('company', ''), 'title': job.get('title', ''),
                'baseline_sha256': base_digest, 'source_sha256': sha(source_path), 'sha256': sha(pdf),
                'track': track, 'method': 'reviewed-fact-ranking', 'artifact': key + '/resume.pdf',
                'delivery': 'application_upload' if job['source'] == 'linkedin' else 'prepared_only_profile_cv_used'}
    for filename, value in [('source.json', tailored), ('manifest.json', metadata)]:
        path = root / filename; temp = path.with_suffix('.tmp'); temp.write_text(json.dumps(value, indent=2)); temp.chmod(0o600); temp.replace(path)
    return pdf, metadata


def verified_variant(data, resume, digest):
    """Only private generated artifacts linked to the current reviewed CV qualify."""
    data, resume = Path(data), Path(resume)
    root = data / 'tailored-resumes'
    if resume.is_symlink() or not re.fullmatch(r'[a-f0-9]{64}', resume.parent.name) or resume.name != 'resume.pdf': return False
    if resume.parent.parent != root or resume.resolve().parent.parent != root.resolve(): return False
    try:
        meta = json.loads(resume.with_name('manifest.json').read_text())
        baseline = data / ('resumes/Karem_Elbostany_Hosting_Support_CV.pdf' if meta['track'] == 'hosting_remote' else 'resume.pdf')
        source_path = data / 'cv-source' / (meta['track'] + '.json')
        return (meta['version'] == VERSION and meta['sha256'] == digest == sha(resume)
                and meta['baseline_sha256'] == sha(baseline) and meta['source_sha256'] == sha(source_path))
    except (OSError, ValueError, KeyError): return False
