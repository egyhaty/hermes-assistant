"""Open an allowlisted board in the existing private browser, preserving its tabs."""
import json
import re
import urllib.parse
import urllib.request

from job_sources import SOURCES


def open_board(source, opener=None):
    if source not in SOURCES:
        raise ValueError('Unsupported job board')
    opener = opener or urllib.request.urlopen
    domain = SOURCES[source]['host'].removeprefix('www.').removeprefix('ae.')
    with opener('http://127.0.0.1:9222/json', timeout=5) as response:
        pages = json.load(response)
    for page in pages:
        host = (urllib.parse.urlsplit(page.get('url', '')).hostname or '').lower()
        page_id = page.get('id', '')
        if (page.get('type') == 'page' and (host == domain or host.endswith('.' + domain))
                and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', page_id)):
            with opener('http://127.0.0.1:9222/json/activate/' + page_id, timeout=5):
                pass
            return {'reused': True}
    url = 'https://' + SOURCES[source]['host'] + '/'
    request = urllib.request.Request('http://127.0.0.1:9222/json/new?' + urllib.parse.quote(url, safe=''), method='PUT')
    with opener(request, timeout=5) as response:
        json.load(response)
    return {'reused': False}
