# Job-specific CVs

Set `JOB_CV_TAILORING=1` after installing private reviewed sources at
`/data/cv-source/devops_uae.json` and `/data/cv-source/hosting_remote.json`.
Each source binds to its reviewed baseline PDF SHA-256. Sources contain personal
data and must never be committed, stored in a ConfigMap, or published.

The current implementation ranks existing summary sentences, skills, first-two
employer bullets, and independent projects against the listing. It preserves all
facts, company attribution, qualifiers, numbers, dates, titles, and education.
It does not generate new claims, infer cloud tenure, or change fit screening.
A changed source invalidates existing upload authorization; a new variant must
be prepared. The profile approval and existing deduplication gates still apply.

Each eligible executed application archives a private PDF, editable source,
manifest, listing identity, and hashes under `/data/tailored-resumes/<id>/`.
LinkedIn uses the variant only when its form acknowledges the application-specific
upload. Other current adapters retain the verified profile CV and mark variants
`prepared_only_profile_cv_used`; preparation is never reported as delivery.

The authenticated reports page exposes the editable source download and links
application records to the archived CV. These contain personal information;
never share the downloads publicly. Historical applications are unchanged.

## Stretch applications

`JOB_APPLICATION_POLICY=stretch` opts the owner into applications above the
verified skill/degree/tenure match. Screening remains recorded, but technical
qualification gaps in DevOps/Linux/infrastructure roles can be treated as
stretch opportunities instead of automatic exclusions. Gaps remain in the
application record; neither CV facts nor form answers are changed to satisfy them.
Nationality, geographical and work-authorization restrictions are not relaxed.
Unattempted matching rejections from an older policy are reconsidered once.
Already-applied, attempted, uncertain and unsupported-flow records are not reset.
The first query includes historical unattempted reviews so reconsideration is not
limited to listings returned on the current search page.

## Email reports

`deploy/jobs-reports.json` runs a separate reporter every five minutes in Dubai
time. It defers while the application controller reports an active batch and
sends the completed batch once. The application worker is not restarted for
report delivery. `--snapshot` explicitly sends a labelled interim report.

The owner recipient and SMTP login live in `hermes-jobs-report-config` Secret
(keys `recipient`, `username`). Gmail authentication references the existing
`hermes-gmail` Secret key `HIMALAYA_APP_PASS`; no credentials are copied into
Git or reports. A narrow network policy permits DNS, authenticated controller
status and STARTTLS SMTP. Pod affinity co-locates the reporter with the worker
for the shared ReadWriteOnce PVC.

Mail includes an Arabic status summary, Dubai timestamps, today's records versus
historical totals, job details, reasons, gaps, missing answers, CV/proof links
requiring Hermes login, recent run outcomes, and a full UTF-8 CSV attachment.
Preparing a CV or clicking Apply is never labelled a confirmed submission.

`/data/email-report-delivery.sqlite3` stores a unique delivery ID and Message-ID.
Only the mail relay's acceptance is recorded as `accepted`; it does not prove
inbox placement. An ambiguous SMTP send becomes `uncertain` and is not retried
automatically. Jobs have no automatic restart retries and concurrency is forbidden.
