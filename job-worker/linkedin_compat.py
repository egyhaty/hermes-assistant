"""Distinguish layout failures from actual browser/session failures."""
from urllib.parse import urlencode


class LinkedInLayoutChanged(RuntimeError):
    pass


def require_supported_layout(driver):
    from selenium.webdriver.support.ui import WebDriverWait
    try:
        WebDriverWait(driver, 20).until(lambda d: d.find_elements('css selector', 'li[data-occludable-job-id]')
                                      or d.find_elements('css selector', 'button[aria-label^="Dismiss "]'))
    except Exception as error:
        if type(error).__name__ != 'TimeoutException':
            raise
    if not driver.find_elements('css selector', 'li[data-occludable-job-id]'):
        raise LinkedInLayoutChanged('LinkedIn search layout is unsupported or listings did not load. Use the multi-site discovery page; no application was started.')


def search_url(term, location, easy_apply_only=True):
    if not location or not str(location).strip():
        raise ValueError('Save a search location before starting. No account-default location is used.')
    params = {'keywords': term, 'location': location}
    if str(location).strip().lower() in ('united arab emirates', 'uae'):
        params['geoId'] = '104305776'
    if easy_apply_only:
        params['f_AL'] = 'true'
    return 'https://www.linkedin.com/jobs/search/?' + urlencode(params)


def failure_reason(error):
    name = type(error).__name__
    if isinstance(error, LinkedInLayoutChanged):
        return str(error)
    if name == 'TimeoutException':
        return 'LinkedIn page timed out or its layout changed. The browser may still be open; check the remote desktop. No submission confirmed.'
    if name in ('NoSuchWindowException', 'InvalidSessionIdException'):
        return 'Browser window closed or session invalid'
    return 'Browser automation error: ' + name
