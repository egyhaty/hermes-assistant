import asyncio
import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'job-worker'))
import serve
from job_sources import Store


class DiscoveryGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        app = web.Application(middlewares=[serve.auth])
        app['discovery_store'] = Store(Path(self.tmp.name) / 'jobs.db')
        app['discovery_term'] = 'DevOps'
        app['discovery_task'] = None
        app['start_lock'] = asyncio.Lock()
        app.router.add_route('*', '/{path:.*}', serve.handle)
        self.app = app
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        serve.SESSIONS['fixture'] = time.time() + 60
        self.headers = {'Cookie': 'jobs_session=fixture', 'Origin': serve.PUBLIC}

    async def asyncTearDown(self):
        task = self.app.get('discovery_task')
        if task:
            await task
        serve.SESSIONS.pop('fixture', None)
        await self.client.close()

    async def test_anonymous_discovery_is_denied(self):
        response = await self.client.get('/jobs/discovery/status', allow_redirects=False)
        self.assertIn(response.status, (401, 303))

    async def test_cross_origin_scan_is_denied(self):
        response = await self.client.post('/jobs/discovery/scan', json={'term': 'DevOps'},
                                          headers=dict(self.headers, Origin='https://evil.test'))
        self.assertEqual(response.status, 403)

    async def test_status_lists_five_boards_without_private_profile(self):
        response = await self.client.get('/jobs/discovery/status', headers=self.headers)
        body = await response.json()
        self.assertEqual(len(body['sources']), 5)
        self.assertNotIn('profile', body)

    async def test_scan_collects_all_boards_without_application_calls(self):
        def fake(source, term):
            return {'source': source, 'term': term, 'status': 'ok', 'message': 'fixture',
                    'checked_at': 10, 'jobs': []}
        with patch.object(serve, 'discover', side_effect=fake) as discover:
            response = await self.client.post('/jobs/discovery/scan', json={'term': 'Linux'}, headers=self.headers)
            self.assertEqual(response.status, 202)
            self.assertEqual((await response.json())['applications_sent'], 0)
            await self.app['discovery_task']
            self.assertEqual(discover.call_count, 5)
        self.assertEqual(len(self.app['discovery_store'].snapshot()['checks']), 5)

    async def test_parallel_scan_is_rejected(self):
        waiting = asyncio.create_task(asyncio.sleep(30))
        self.app['discovery_task'] = waiting
        try:
            response = await self.client.post('/jobs/discovery/scan', json={'term': 'Linux'}, headers=self.headers)
            self.assertEqual(response.status, 409)
        finally:
            waiting.cancel()
            try:
                await waiting
            except asyncio.CancelledError:
                pass
            self.app['discovery_task'] = None

    async def test_invalid_input_does_not_start_collection(self):
        for payload in ({'term': ''}, {'term': 'x' * 101}, {'term': []}, []):
            response = await self.client.post('/jobs/discovery/scan', json=payload, headers=self.headers)
            self.assertEqual(response.status, 400)
        self.assertIsNone(self.app['discovery_task'])

    async def test_open_site_cannot_navigate_to_arbitrary_urls(self):
        response = await self.client.post('/jobs/discovery/open-site', json={'source':'https://evil.test'}, headers=self.headers)
        self.assertEqual(response.status,400)
