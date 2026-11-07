# CODEX HANDOFF — FINISH AND DEPLOY HERMES JOBS V2

## Owner directive
Upgrade the EXISTING live jobs system at https://hermes.murabba.net/jobs/ in place. Preserve its browser automation, login/session state, database, security profiles, job history, ingress and four scheduled cycles/day. Do not replace with a toy/demo page. Owner wants first verified real applications, with CV customized per job and cover letter when appropriate, without fabricating credentials. Implement, test, deploy and report actual receipts. Do not falsely claim success.

## What ChatGPT already did
- Inspected repo `egyhaty/hermes-assistant`, particularly `deploy/jobs.json` and `deploy/kustomization.yaml`.
- Verified deployment has `hermes-jobs` service on port 9118, ingress path `/jobs/`, GHCR image pinned to `sha256:01c344925a7cca54996035351d5b870e4e0c2d6c9c60cd4a9bbea22156b270f9`, Kubernetes security profiles, PVC `hermes-data`.
- Existing CronJob `hermes-jobs-schedule` is every six hours, Cairo timezone; base manifest says suspend=true, kustomization patches suspend=false. This is configuration, NOT proof of successful runs.
- Draft PR #2, branch `feature/jobs-v2-product`: `docs/JOBS-V2.md` acceptance contract, `jobs_v2/tailoring.py` evidence-locked text draft tailoring, `jobs_v2/package.py` per-job package/manifest, `tests/test_jobs_v2_tailoring.py`, `.github/workflows/jobs-v2-checks.yml`.
- These are INITIAL components only. They have NOT been integrated into live worker, have not generated PDFs, and have not been deployed. Check CI results.
- An illustrative local HTML demo was generated outside repository; NOT the desired production UI.

## Immediate investigation (do this yourself)
1. Find actual source and Dockerfile for the existing GHCR jobs image. It was NOT found under guessed paths `jobs/` in the visible repo. Inspect full checkout, Git history, CI, image labels, image filesystem if authorized, and adjacent workspaces. Determine real build and deployment workflow.
2. Inspect live cluster safely: `kubectl -n hermes get deploy,cronjob,jobs,pods,ingress`, inspect scheduler and worker logs, current /health, PVC backup, existing job records, actual application receipts. Never print secrets.
3. Preserve a rollback image digest and data backup before modifications.
4. Connect private approved resume source, not fabricated data and not committed to public repo. If final CV is absent, retrieve it from owner/secure existing deployment and request only missing approval.

## Feature requirements
- Job-specific ATS-friendly resume with truthful reorder/rephrasing; distinguish professional Linux experience vs personal AWS/Terraform/Kubernetes labs vs basic Azure/Ansible. Never claim production Azure or advanced Python/Ansible.
- Optional targeted cover letter based on job posting, no invented claims.
- Render real PDF/DOCX, store per-job artifact version/hash privately, preview in existing UI.
- Source discovery, canonical URL dedup, suitability scoring and reason codes; filter UAE Dubai/Sharjah/Ajman and senior Linux/infra/cloud ops/DevOps/SRE roles.
- State machine and receipts: discovered, scored, draft, needs-approval, submitting, confirmed-submitted, failed, needs-human. Do not confuse clicking submit with confirmed receipt.
- Browser executor retains existing session, obeys MFA/CAPTCHA/website restrictions; human approval for unknown screening questions or sensitive commitments.
- Add run health, queue, counts, last errors, application status, download/preview tailored CV and cover letter to existing /jobs/ dashboard.
- Bounded retries, backoff, daily caps, kill switch, audit log, notifications. Avoid duplicate applications.
- Pilot: first five real submissions require explicit owner approval; after verified receipts and owner signoff, enable scoped automatic submissions. No blind mass applications.

## Deploy and verification
Run unit/integration tests and existing regression suite, build digest-pinned GHCR image, canary rollout in hermes namespace, validate browser UI /jobs/, run one dry-run then owner-approved live submission, capture actual receipts, verify scheduled runs and rollback ability. Report URLs, image digest, run timestamps, confirmed applications and remaining blockers.

## Working agreement
User is impatient with plans and fake progress. EXECUTE as much as environment allows, avoid repeated questions, do not report deploy if not done. Open/update PR #2 with real implementation and evidence; keep a short Arabic progress summary. If Codex cannot access cluster or original worker source, say exactly what permission or path is missing.
