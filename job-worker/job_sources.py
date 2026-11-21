"""Public job discovery. This module never signs in, fills forms or submits applications."""
import csv
import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

SOURCES = {
    'linkedin': {'name': 'LinkedIn', 'host': 'www.linkedin.com'},
    'indeed': {'name': 'Indeed', 'host': 'ae.indeed.com'},
    'bayt': {'name': 'Bayt', 'host': 'www.bayt.com'},
    'naukrigulf': {'name': 'NaukriGulf', 'host': 'www.naukrigulf.com'},
    'gulftalent': {'name': 'GulfTalent', 'host': 'www.gulftalent.com'},
}
MAX_BYTES = 3 * 1024 * 1024


def search_url(source, term):
    term = str(term).strip()
    if source not in SOURCES or not term or len(term) > 100:
        raise ValueError('Choose a supported site and a search term of 1–100 characters.')
    slug = urllib.parse.quote(re.sub(r'[^a-z0-9]+', '-', term.lower()).strip('-'))
    if source == 'linkedin':
        return 'https://www.linkedin.com/jobs/search/?' + urllib.parse.urlencode({
            'keywords': term, 'location': 'United Arab Emirates', 'geoId': '104305776'})
    if source == 'indeed':
        return 'https://ae.indeed.com/jobs?' + urllib.parse.urlencode({'q': term, 'l': 'United Arab Emirates'})
    if source == 'bayt':
        return f'https://www.bayt.com/en/uae/jobs/{slug}-jobs/'
    if source == 'naukrigulf':
        return f'https://www.naukrigulf.com/{slug}-jobs-in-uae'
    return 'https://www.gulftalent.com/uae/jobs?' + urllib.parse.urlencode({'keywords': term})


def fetch_url(source, term):
    url = search_url(source, term)
    if source == 'linkedin':
        url = url.replace('/jobs/search/', '/jobs-guest/jobs/api/seeMoreJobPostings/search') + '&start=0'
    return url


def canonical_url(source, url):
    """Accept only public job links on the selected board, with tracking removed."""
    if source not in SOURCES:
        return None
    p = urllib.parse.urlsplit(urllib.parse.urljoin('https://' + SOURCES[source]['host'], url))
    host = (p.hostname or '').lower()
    domain = SOURCES[source]['host'].removeprefix('www.').removeprefix('ae.')
    if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
        return None
    if host != domain and not host.endswith('.' + domain):
        return None
    patterns = {'linkedin': r'/jobs/view/(?:[^/]*-)?(\d+)',
                'bayt': r'/jobs/[^/]+-(\d+)/?',
                'naukrigulf': r'-jid-(\d+)(?:$|[/?])',
                'gulftalent': r'/jobs/[^/]+-(\d+)(?:$|[/?])'}
    if source == 'indeed':
        job_id = urllib.parse.parse_qs(p.query).get('jk', [''])[0]
        if not re.fullmatch(r'[a-zA-Z0-9]{6,40}', job_id):
            return None
        return 'https://ae.indeed.com/viewjob?jk=' + job_id
    match = re.search(patterns[source], p.path)
    if not match:
        return None
    if source == 'linkedin':
        return 'https://www.linkedin.com/jobs/view/' + match[1] + '/'
    return urllib.parse.urlunsplit(('https', SOURCES[source]['host'], p.path, '', ''))


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self):
        return ' '.join(x.text() if isinstance(x, Node) else x for x in self.children).strip()


class Document(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'wbr'}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = self.current = Node()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in self.VOID:
            self.current = node

    def handle_endtag(self, tag):
        node = self.current
        while node.parent:
            if node.tag == tag:
                self.current = node.parent
                break
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def _location(value):
    if isinstance(value, list):
        return '; '.join(filter(None, (_location(x) for x in value)))
    if isinstance(value, dict):
        address = value.get('address', value)
        if isinstance(address, str):
            return address
        return ', '.join(str(address[k]) for k in ('addressLocality', 'addressRegion', 'addressCountry')
                         if address.get(k) and isinstance(address[k], str))
    return value if isinstance(value, str) else ''


def is_uae(location):
    return bool(re.search(r'\b(UAE|United Arab Emirates|Dubai|Abu Dhabi|Sharjah|Ajman|Fujairah|Ras Al Khaimah|Umm Al Quwain|AE)\b', location, re.I))


def parse_jobs(source, html):
    doc = Document(html)
    found = {}

    def add(url, title, company='', location=''):
        link = canonical_url(source, str(url))
        title = re.sub(r'\s+', ' ', str(title)).strip()[:240]
        if not link or not title:
            return
        record = {'source': source, 'url': link, 'title': title, 'company': str(company)[:240],
                  'location': str(location)[:240], 'location_verified': is_uae(str(location)),
                  'application_status': 'not_applied'}
        # Prefer structured metadata over a title-only link.
        if link not in found or (company and not found[link]['company']):
            found[link] = record

    def structured(value):
        if isinstance(value, list):
            for item in value:
                structured(item)
        elif isinstance(value, dict):
            types = value.get('@type', [])
            if 'JobPosting' in ([types] if isinstance(types, str) else types):
                org = value.get('hiringOrganization', {})
                add(value.get('url', ''), value.get('title', ''),
                    org.get('name', '') if isinstance(org, dict) else org, _location(value.get('jobLocation', '')))
            for key in ('@graph', 'itemListElement', 'item'):
                if key in value:
                    structured(value[key])

    for node in doc.root.walk():
        if node.tag == 'script' and node.attrs.get('type') == 'application/ld+json':
            try:
                structured(json.loads(node.text()))
            except (ValueError, TypeError):
                pass
    for node in doc.root.walk():
        if node.tag != 'a' or not canonical_url(source, node.attrs.get('href', '')):
            continue
        card = node
        while card.parent:
            if card.tag in ('li', 'article') or 'data-job-id' in card.attrs or 'base-card' in card.attrs.get('class', '').split():
                break
            card = card.parent
        # Do not take unrelated company/location text from an entire search page.
        descendants = list(card.walk()) if card is not doc.root else []
        def field(class_part):
            return next((x.text() for x in descendants if class_part in x.attrs.get('class', '')), '')
        title = node.text() or next((x.text() for x in descendants if x.tag in ('h2', 'h3')), '')
        if source == 'linkedin':
            title = field('base-search-card__title') or title
        add(node.attrs['href'], title,
            field('base-search-card__subtitle') if source == 'linkedin' else '',
            field('job-search-card__location') if source == 'linkedin' else '')
    return list(found.values())[:100]


class BoardRedirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, host):
        self.host = host

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p = urllib.parse.urlsplit(newurl)
        if p.scheme != 'https' or p.hostname != self.host:
            raise ValueError('Site redirected outside its configured public search host.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def discover(source, term, opener=None):
    url = fetch_url(source, term)
    result = {'source': source, 'term': term, 'search_url': search_url(source, term),
              'checked_at': int(time.time()), 'jobs': [], 'status': 'error'}
    try:
        opener = opener or urllib.request.build_opener(BoardRedirects(urllib.parse.urlsplit(url).hostname)).open
        req = urllib.request.Request(url, headers={'User-Agent': 'HermesJobDiscovery/1.0', 'Accept': 'text/html'})
        with opener(req, timeout=15) as response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('Search page exceeded the size limit.')
            html = raw.decode('utf-8', errors='replace')
        if re.search(r'<title>[^<]*(captcha|just a moment|access denied|security check)', html, re.I):
            result.update(status='action_required', message='Site requires a manual security check. No bypass attempted.')
        else:
            jobs = parse_jobs(source, html)
            result.update(jobs=jobs, status='ok' if jobs else 'unrecognized',
                          message=f'{len(jobs)} listings collected; no applications sent.' if jobs else 'No recognizable listings. Empty results and a changed layout cannot yet be distinguished.')
    except urllib.error.HTTPError as error:
        result.update(status='action_required' if error.code in (401, 403, 429) else 'error',
                      message=f'Site returned HTTP {error.code}. No automatic retries or access bypass.')
    except (OSError, ValueError) as error:
        result['message'] = 'Search unavailable: ' + type(error).__name__
    return result


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (url TEXT PRIMARY KEY, source TEXT, payload TEXT, first_seen INTEGER, last_seen INTEGER)')
            db.execute('CREATE TABLE IF NOT EXISTS checks (source TEXT, term TEXT, payload TEXT, PRIMARY KEY(source,term))')

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def save(self, result):
        with self.connect() as db:
            for job in result['jobs']:
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET payload=excluded.payload,last_seen=excluded.last_seen',
                           (job['url'], job['source'], json.dumps(job), result['checked_at'], result['checked_at']))
            summary = {k: v for k, v in result.items() if k != 'jobs'}
            summary['count'] = len(result['jobs'])
            db.execute('INSERT OR REPLACE INTO checks VALUES (?,?,?)', (result['source'], result['term'], json.dumps(summary)))

    def snapshot(self, history_path=None):
        with self.connect() as db:
            jobs = [dict(json.loads(row[0]), first_seen=row[1], last_seen=row[2]) for row in db.execute('SELECT payload,first_seen,last_seen FROM jobs ORDER BY last_seen DESC LIMIT 500')]
            checks = [json.loads(row[0]) for row in db.execute('SELECT payload FROM checks ORDER BY source,term')]
        history = set()
        if history_path and Path(history_path).is_file():
            with Path(history_path).open(encoding='utf-8-sig', errors='replace') as stream:
                for row in csv.DictReader(stream):
                    url = canonical_url('linkedin', row.get('Job Link', ''))
                    if not url and str(row.get('Job ID', '')).isdigit():
                        url = canonical_url('linkedin', '/jobs/view/' + row['Job ID'] + '/')
                    if url:
                        history.add(url)
        for job in jobs:
            if job['url'] in history:
                # Old CSV entries are evidence of prior handling, not confirmation
                # that the platform accepted a submission.
                job['application_status'] = 'recorded_in_legacy_history'
        return {'jobs': jobs, 'checks': checks}
