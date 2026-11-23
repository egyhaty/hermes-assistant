"""Owner-authorized stretch applications, without converting gaps into claims."""
import copy
import re

POLICY = 'stretch-devops-v1'
ROLE = re.compile(r'devops|\bSRE\b|site reliability|platform engineer|linux|infrastructure|infra engineer', re.I)
OUTSIDE = re.compile(r'civil|construction|mechanical|structural|roads?|facilit|backend|frontend|full.?stack|data scien|AI systems|smart home|sales', re.I)


def stretch_review(job, decision, scope='devops_uae'):
    out = copy.deepcopy(decision)
    out['application_policy'] = POLICY
    if out['eligible'] or scope != 'devops_uae': return out
    title = job.get('title', '')
    text = title + '\n' + job.get('description', '') + '\n' + job.get('head', '')
    if not ROLE.search(title) or OUTSIDE.search(title): return out
    # Career/technology/degree gaps may be acceptable to an employer. Legal,
    # nationality and geographic restrictions are not relaxed by this policy.
    if re.search(r'Emirati|Emiratisation|UAE nationals?|UAE citizens?|nationali[sz]ation', text, re.I): return out
    if re.search(r'(?:must|required to) (?:reside|be based|relocate|work on.?site) in (?:Pakistan|India|UK|United Kingdom|US|USA|United States|Europe|Canada)', text, re.I): return out
    reasons = ' '.join([out.get('reason','')] + out.get('required_unknown', []))
    if re.search(r'conflicting|country.restricted|outside (?:the )?UAE|restricted to|not (?:in|inside) (?:the )?UAE|citizenship|security clearance|legally|work authori[sz]ation|work permit|sponsorship', reasons, re.I): return out
    out['gaps'] = list(dict.fromkeys(out.get('gaps', []) + out.get('required_unknown', [])))
    out['required_unknown'] = []
    out['eligible'] = True
    out['stretch'] = True
    out['original_fit_reason'] = decision['reason']
    out['reason'] = 'Owner-authorized stretch application for a DevOps/Linux/infrastructure role. Qualification gaps remain explicit; the CV and form answers must use verified facts only.'
    return out
