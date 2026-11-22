"""Small loopback-only CDP client for the worker's normal persistent Chromium."""
import json
import time
import urllib.parse
import urllib.request

import websocket

HOSTS = {'www.naukrigulf.com', 'www.linkedin.com', 'www.bayt.com', 'www.gulftalent.com', 'ae.indeed.com', 'profile.indeed.com'}


def allowed_url(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme == 'https' and p.hostname in HOSTS and not p.username and not p.password and p.port in (None, 443)


class BrowserPage:
    def __init__(self, host):
        if host not in HOSTS:
            raise ValueError('Unsupported board host')
        with urllib.request.urlopen('http://127.0.0.1:9222/json', timeout=5) as response:
            pages = json.load(response)
        page = next((p for p in pages if p.get('type') == 'page' and urllib.parse.urlsplit(p.get('url', '')).hostname == host), None)
        if page is None:
            req = urllib.request.Request('http://127.0.0.1:9222/json/new?' + urllib.parse.quote('https://' + host + '/', safe=''), method='PUT')
            with urllib.request.urlopen(req, timeout=5) as response:
                page = json.load(response)
        ws_url = urllib.parse.urlsplit(page['webSocketDebuggerUrl'])
        if ws_url.hostname not in ('127.0.0.1', 'localhost') or ws_url.port != 9222:
            raise ValueError('Unexpected debugging endpoint')
        self.ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=25, suppress_origin=True)
        self.seq = 0

    def call(self, method, **params):
        self.seq += 1
        self.ws.send(json.dumps({'id': self.seq, 'method': method, 'params': params}))
        while True:
            response = json.loads(self.ws.recv())
            if response.get('id') == self.seq:
                if response.get('error'):
                    raise RuntimeError(response['error'].get('message', 'Browser request failed'))
                return response.get('result', {})

    def js(self, code):
        result = self.call('Runtime.evaluate', expression=code, returnByValue=True, awaitPromise=True)
        if result.get('exceptionDetails'):
            raise RuntimeError('Browser page operation failed')
        return result.get('result', {}).get('value')

    def goto(self, url):
        if not allowed_url(url):
            raise ValueError('Navigation outside configured job boards is disabled')
        self.call('Page.bringToFront')
        self.call('Page.navigate', url=url)
        time.sleep(3)

    def wait(self, expression, seconds=20):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            try:
                # Serializing a DOM node can fail with "Object reference chain
                # is too long"; readiness expressions need only a boolean.
                if self.js('!!(' + expression + ')'):
                    return True
            except RuntimeError as error:
                if not any(word in str(error).lower() for word in ('context', 'page operation failed', 'navigated or closed')):
                    raise
            time.sleep(1)
        return False

    def close(self):
        self.ws.close()
