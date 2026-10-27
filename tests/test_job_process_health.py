import importlib.util
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('process_health', ROOT/'job-worker/process_health.py')
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


class ProcessHealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='jobs-x11-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'.X11-unix').mkdir()
        self.endpoint = self.root/'.X11-unix/X99'
        self.lock = self.root/'.X99-lock'

    def stale_files(self, pid):
        self.lock.write_text(str(pid))
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(self.endpoint))

    def test_container_restart_removes_dead_display_state_only(self):
        child = subprocess.Popen([sys.executable, '-c', 'pass'])
        child.wait()
        self.stale_files(child.pid)
        unrelated = self.root/'keep-me'
        unrelated.write_text('persistent session marker')
        health.clean_stale_display(self.root)
        self.assertFalse(self.lock.exists())
        self.assertFalse(self.endpoint.exists())
        self.assertEqual(unrelated.read_text(), 'persistent session marker')

    def test_active_display_is_never_removed(self):
        self.lock.write_text('123')
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(self.endpoint))
            server.listen()
            with self.assertRaisesRegex(RuntimeError, 'active'):
                health.clean_stale_display(self.root)
        self.assertTrue(self.lock.exists())
        self.assertTrue(self.endpoint.exists())

    def test_live_lock_owner_is_not_removed(self):
        self.stale_files(os.getpid())
        with self.assertRaisesRegex(RuntimeError, 'alive'):
            health.clean_stale_display(self.root)
        self.assertTrue(self.lock.exists())

    def test_corrupt_lock_requires_inspection(self):
        self.lock.write_text('not-a-pid')
        with self.assertRaisesRegex(RuntimeError, 'Invalid'):
            health.clean_stale_display(self.root)
        self.assertTrue(self.lock.exists())

    def test_zombie_child_is_reaped_and_reported(self):
        child = subprocess.Popen([sys.executable, '-c', 'raise SystemExit(7)'])
        child.wait()
        failed = health.failed_children([child])
        self.assertEqual(failed, [{'name': Path(sys.executable).name, 'exit_code': 7}])

    def test_startup_fails_if_display_child_exits(self):
        child = subprocess.Popen([sys.executable, '-c', 'raise SystemExit(2)'])
        child.wait()
        with self.assertRaisesRegex(RuntimeError, 'exited during startup'):
            health.wait_for_display(child, self.endpoint, timeout=0.2)

    def test_startup_succeeds_only_with_live_display_socket(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        self.addCleanup(child.wait)
        self.addCleanup(child.terminate)
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(self.endpoint))
            server.listen()
            health.wait_for_display(child, self.endpoint, timeout=0.2)

    def test_render_has_bounded_startup_and_automatic_recovery(self):
        spec = importlib.util.spec_from_file_location('render', ROOT/'job-worker/render.py')
        render = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(render)
        items = render.render('ghcr.io/example/jobs@sha256:'+'a'*64)['items']
        deployment = next(x for x in items if x['kind'] == 'Deployment')
        container = deployment['spec']['template']['spec']['containers'][0]
        for name in ('startupProbe', 'readinessProbe', 'livenessProbe'):
            self.assertEqual(container[name]['httpGet'], {'path': '/health', 'port': 9118})
            self.assertGreater(container[name]['timeoutSeconds'], 2)
        self.assertGreaterEqual(container['startupProbe']['failureThreshold'] * container['startupProbe']['periodSeconds'], 60)


if __name__ == '__main__':
    unittest.main()
