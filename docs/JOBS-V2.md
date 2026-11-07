# Hermes Jobs v2 — implementation contract

## Existing infrastructure (verified from deploy/jobs.json)
- Worker Deployment and HTTP Service on 9118, routed through https://hermes.murabba.net/jobs/
- Six-hour Kubernetes CronJob with concurrencyPolicy=Forbid; kustomization enables it
- Browser security profiles, secret-based authentication, persistent worker data
- Deployment existence does **not** prove successful external applications

## Product upgrades (build in this order)
1. **Operations dashboard:** show latest scheduler run, worker health, number discovered, ranked, attempted, confirmed, failed, awaiting owner. Display timestamps and last error without leaking secrets. No synthetic counters.
2. **Pipeline with explicit states:** discovered → normalized → scored → queued → approved/auto-eligible → submitting → submitted/failed/needs-human. Enforce valid transitions and idempotency using company + source job ID + normalized URL.
3. **Explainable ranking:** score Linux/Infrastructure/Cloud Operations/SRE/DevOps based on verified experience. Exclude false claims about Azure production, Python/SQLite expertise and advanced Ansible. Mark missing screening answers as blockers.
4. **Application receipts:** persist job URL, employer, role, CV hash/version, screening answer set, timestamp, confirmation page or reference number, status and error class. Distinguish clicked Submit from externally confirmed submission.
5. **Browser executor:** site-specific adapters, bounded retries, per-domain throttling, timeout and screenshot on failure. Never bypass CAPTCHA or access restrictions. Pause on account login, MFA, sensitive questions or unclear consent.
6. **Owner controls:** pause/resume auto-apply, source allowlist, minimum score (initially 80), daily cap, editable approved answer templates, and dry-run mode.
7. **Pilot gate:** first five real applications require owner approval and confirmation. Only enable automatic submissions for validated sources/answers after owner approval.
8. **Notifications:** daily Egyptian Arabic summary of confirmed submissions, failures, pending approvals and recruiter follow-ups; avoid duplicates.
9. **Security and deployment:** secrets in K8s Secret, CSRF/session protection for dashboard controls, audit trail, backups, health probes, canary/rollback, and tests before Argo sync.

## Acceptance tests
- Mock job source yields duplicates, expired jobs, missing fields, matching/nonmatching jobs.
- Scoring is deterministic, transparent, and never invents experience.
- Duplicate job cannot submit twice even after worker restart.
- Unanswered screening question and CAPTCHA block submission.
- Fake successful button click without confirmation is not marked submitted.
- Dashboard numbers reconcile to persisted receipts and actual CronJob run history.
- First five live submissions are individually approved by owner and verified.
- Existing worker and gateway continue working through rollback.

## Implementation note
This file defines the upgrade work; it does not implement the features or deploy them.
