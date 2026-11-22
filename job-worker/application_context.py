"""Keep the final browser action attached to the job that was actually reviewed."""
from job_sources import canonical_url


def require_reviewed_page(page, job):
    if canonical_url(job['source'], (page.read if hasattr(page, 'read') else page.js)('location.href')) != job['url']:
        raise RuntimeError('The browser left the reviewed job; no application attempted')
