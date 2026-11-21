# Multi-site job discovery and sign-in

The authenticated `/jobs/` page has a board registry for LinkedIn, Indeed,
Bayt, NaukriGulf and GulfTalent. These are discovery connectors, not five
working application adapters.

## What is implemented

- Bounded public search using job keywords and UAE location routes. The
  LinkedIn request includes UAE geoId `104305776` rather than relying on the
  account's default location.
- Structured JobPosting parsing plus board-specific job-link recognition.
  Listings without an extracted UAE location remain unverified.
- Canonical URLs and SQLite upserts prevent repeated collection of the same
  board listing. This does not yet resolve reposts across different boards.
- Existing LinkedIn CSV history is labelled as previously handled. Historical
  records are not retrospectively claimed as verified submissions.
- Site-level HTTP errors, security checks, timeouts and unrecognised layouts
  remain visible. HTTP 403 is not treated as an empty successful search.
- A `Sign in on worker` action opens an allowlisted board homepage in the
  persistent Chromium browser via loopback CDP. It never receives passwords
  or OTPs. Opening a page does not prove authentication succeeded.
- Existing authenticated UI sessions and browser POST Origin checks protect
  discovery and browser-navigation actions. Opening a board is refused while
  an application run is active.

Public discovery does not use or export browser cookies. Signing in prepares
the browser for future application adapters; it does not change HTTP search
access or make an application adapter available.

## LinkedIn incident

On 2026-11-22 the account's search redirected to `/jobs/search-results/`,
using `componentkey="job-card-component-ref-…"` rather than the old
`li[data-occludable-job-id]` elements. The upstream Selenium wait timed out.
Its broad WebDriverException handler incorrectly described the timeout as
a closed browser and could exit with code zero.

The compatibility patch provides an explicit location before navigation,
checks whether the old application layout is available, records a truthful
layout/timeout reason, and exits nonzero for caught failures. This is failure
diagnosis and containment; it is not a replacement application adapter for
LinkedIn's new search and form layouts.

## Owner sign-in

1. Sign in to Hermes and open `/jobs/`.
2. Choose `Sign in on worker` on a board card.
3. In the private desktop, sign in on that board using its normal process.
4. Enter any MFA or CAPTCHA yourself; leave the browser signed in.
5. Repeat for each board. Do not send passwords, OTPs, cookies or session
   exports through chat.

The Chromium profile remains on the existing worker PVC. A board may still
expire or challenge a session; unattended perpetual login is not guaranteed.

## Remaining work before unattended multi-site applications

Each site needs its own authenticated search, job-detail, form, unknown-answer,
resume-upload, confirmation and application-history adapters. LinkedIn's new
layout needs these compatibility checks too. Account access must be checked
in the persistent browser before testing real site flows. No application was
sent to validate discovery or sign-in navigation.

## Verification

The job-worker unittest suite exercises source URL validation, redirect
restrictions, parsing, unknown locations, HTTP 403 handling, storage/history,
gateway authentication/Origin checks and collection overlap. Fixtures test
parser contracts; they do not certify live compatibility with every site.
The pinned upstream is patched and compiled in the image build, followed by
the existing image vulnerability scan. Production rollout requires an
immutable digest from a successful build and preservation of the existing
worker recovery probes and sandbox settings.
