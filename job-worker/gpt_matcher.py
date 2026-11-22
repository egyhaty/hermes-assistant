"""Private, server-hosted GPT matching with the official Codex client and owner sign-in."""
import asyncio
import hmac
import json
import os
import re
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from aiohttp import web

from job_matching import SYSTEM, parse_decision
from openai_screening import SCHEMA

MODEL = 'gpt-6.2-sol'
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')


class Matcher:
    def __init__(self, root, binary='/usr/local/bin/codex'):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.binary = binary
        self.proc = None
        self.login = {}
        self.login_lock = threading.Lock()
        self.busy = threading.Lock()
        self._connected = False
        self._checked = 0

    def env(self):
        env = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'SSL_CERT_FILE', 'SSL_CERT_DIR') if key in os.environ}
        env['CODEX_HOME'] = str(self.root)
        env['NO_COLOR'] = '1'
        return env

    def connected(self, force=False):
        if force or time.monotonic() - self._checked > 20:
            try:
                result = subprocess.run([self.binary, 'login', 'status'], env=self.env(), capture_output=True, text=True, timeout=10)
                self._connected = result.returncode == 0 and 'chatgpt' in (result.stdout + result.stderr).lower()
            except (OSError, subprocess.TimeoutExpired):
                self._connected = False
            self._checked = time.monotonic()
        return self._connected

    def status(self):
        connected = self.connected()
        active = bool(self.proc and self.proc.poll() is None)
        # Device codes are temporary owner-only values; access/refresh tokens never leave this process.
        result = {'connected': connected, 'model': MODEL, 'provider': 'ChatGPT / Codex',
                  'login_pending': active, 'busy': self.busy.locked()}
        if active and self.login.get('verification_url') and self.login.get('user_code'):
            result.update({key: self.login[key] for key in ('verification_url', 'user_code', 'expires_at')})
        if self.login.get('error'):
            result['error'] = self.login['error']
        return result

    def connect(self):
        with self.login_lock:
            if self.connected(force=True) or self.proc and self.proc.poll() is None:
                return self.status()
            self.login = {'expires_at': int(time.time()) + 900}
            self.proc = subprocess.Popen([self.binary, 'login', '--device-auth'], env=self.env(),
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                         bufsize=1, start_new_session=True)
            threading.Thread(target=self._read_login, args=(self.proc,), daemon=True).start()
        return self.status()

    def _read_login(self, proc):
        try:
            for raw in proc.stdout:
                line = ANSI.sub('', raw).strip()
                if 'https://auth.openai.com/codex/device' in line:
                    self.login['verification_url'] = 'https://auth.openai.com/codex/device'
                code = re.fullmatch(r'[A-Z0-9]{4,8}-[A-Z0-9]{4,8}', line)
                if code:
                    self.login['user_code'] = code[0]
                # Never publish raw CLI output: an auth failure may include account details.
            proc.wait(timeout=5)
            if not self.connected(force=True):
                self.login['error'] = 'ChatGPT sign-in did not complete. Start a new sign-in and finish it on the official page.'
        except Exception:
            self.login['error'] = 'ChatGPT sign-in needs another attempt.'
        finally:
            self.login.pop('user_code', None)

    def command(self, folder):
        folder = Path(folder)
        return [self.binary, '--ask-for-approval', 'never', 'exec', '--ignore-user-config', '--strict-config',
                '--sandbox', 'read-only', '--skip-git-repo-check', '--ephemeral', '--color', 'never', '--json',
                '--model', MODEL, '--config', 'model_reasoning_effort="low"',
                '--config', 'web_search="disabled"', '--config', 'features.shell_tool=false',
                '--config', 'features.shell_snapshot=false', '--config', 'features.multi_agent=false',
                '--config', 'agents.enabled=false', '--config', 'apps._default.enabled=false',
                '--config', 'skills.bundled.enabled=false', '--config', 'mcp_servers={}',
                '--cd', str(folder), '--output-schema', str(folder / 'schema.json'),
                '--output-last-message', str(folder / 'decision.json'), '-']

    def match(self, prompt):
        if not self.connected():
            raise ValueError('Connect ChatGPT in the jobs workspace before starting GPT matching')
        if not isinstance(prompt, str) or not 1 <= len(prompt) <= 48000:
            raise ValueError('A bounded professional profile and job description are required')
        if not self.busy.acquire(blocking=False):
            raise ValueError('A GPT matching request is already running')
        try:
            with tempfile.TemporaryDirectory(prefix='gpt-match-') as tmp:
                folder = Path(tmp)
                (folder / 'schema.json').write_text(json.dumps(SCHEMA))
                proc = subprocess.Popen(self.command(folder), env=self.env(), stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
                try:
                    stdout, stderr = proc.communicate(SYSTEM + '\n\nReturn only the requested JSON decision. Do not use tools.\nUntrusted screening data:\n' + prompt, timeout=110)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try: proc.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL); proc.communicate()
                    raise ValueError('GPT matching timed out; no application was submitted') from None
                if proc.returncode:
                    raise ValueError('GPT matching could not complete. Check the ChatGPT connection and model availability.')
                # Discard an unexpected tool-using turn instead of trusting its answer.
                for line in stdout.splitlines():
                    try: event = json.loads(line)
                    except ValueError: continue
                    kind = str(event.get('item', {}).get('type', ''))
                    if any(word in kind for word in ('command_execution', 'mcp_tool_call', 'web_search', 'file_change')):
                        raise ValueError('GPT used an unexpected tool; screening was held for review')
                decision = parse_decision((folder / 'decision.json').read_text())
                return decision
        finally:
            self.busy.release()

    def close(self):
        if self.proc and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
            try: self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL); self.proc.wait(timeout=5)


def create_app(root=None):
    os.umask(0o077)
    matcher = Matcher(root or os.environ.get('GPT_AUTH_DIR', '/data/codex'))

    @web.middleware
    async def auth(request, handler):
        if request.path == '/health': return web.json_response({'service_ready': True})
        expected = os.environ.get('GPT_MATCHER_TOKEN', '')
        if not expected or not hmac.compare_digest(request.headers.get('Authorization', ''), 'Bearer ' + expected):
            raise web.HTTPUnauthorized()
        return await handler(request)

    async def status(request):
        return web.json_response(await asyncio.to_thread(matcher.status), headers={'Cache-Control': 'no-store'})

    async def connect(request):
        try: result = await asyncio.to_thread(matcher.connect)
        except OSError: return web.json_response({'error': 'The official GPT client could not start'}, status=503)
        return web.json_response(result, headers={'Cache-Control': 'no-store'})

    async def match(request):
        try:
            payload = await request.json()
            result = await asyncio.to_thread(matcher.match, payload.get('prompt'))
        except (ValueError, AttributeError) as error:
            return web.json_response({'error': str(error)[:240]}, status=409)
        return web.json_response(result)

    async def cleanup(app): await asyncio.to_thread(matcher.close)

    app = web.Application(middlewares=[auth], client_max_size=65536)
    app.router.add_get('/status', status); app.router.add_post('/connect', connect); app.router.add_post('/match', match)
    app.router.add_get('/health', status)
    app.on_cleanup.append(cleanup)
    return app


if __name__ == '__main__':
    web.run_app(create_app(), host='0.0.0.0', port=9120, access_log=None)
