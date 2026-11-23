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
