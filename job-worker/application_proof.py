"""Keep platform screenshots private and local to the worker's evidence directory."""
import base64
import hashlib
import os
import time
from pathlib import Path


def capture(page, url):
    try:
        data = base64.b64decode(page.call('Page.captureScreenshot', format='png')['data'], validate=True)
        if not data.startswith(b'\x89PNG\r\n\x1a\n'): return None
        folder = Path(os.environ.get('JOB_DATA', '/data')) / 'application-evidence'
        folder.mkdir(exist_ok=True, mode=0o700)
        name = hashlib.sha256(url.encode()).hexdigest()[:20] + '-' + str(time.time_ns()) + '.png'
        target = folder / name; target.write_bytes(data); target.chmod(0o600)
        return name
    except Exception:
        # An evidence-image failure cannot erase a platform-confirmed submission.
        return None
