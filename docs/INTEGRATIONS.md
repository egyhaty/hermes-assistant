# Integration state — 2026-10-26

## Firecrawl
Built-in keyless Firecrawl selected for search and extraction. Public Kubernetes documentation search and scrape passed. No API key or paid provider configured for these tests. Keyless availability is upstream controlled.

## Kanban
Persistent boards: karem-work, karem-study, karem-personal. Existing current board preserved. Integration cards initially blocked; automatic dispatch, review dispatch, notification and subscription disabled in managed configuration. No scheduled jobs created.

## Langfuse
Official plugin version 2.0.0 pinned to NousResearch/hermes-official-plugins commit e1f16143f164c4db10ea8fc0fc47ff8ac611e9fc. Official installer resolved dependencies; doctor passed import and registration of 11 hooks. Capture explicitly set to metadata in the live private dotenv. Project credentials stored in dedicated Kubernetes Secret and wired to the gateway only. HERMES_LANGFUSE_CAPTURE=metadata is enforced in gateway environment; end_user_attribution=false in managed configuration. Deployment rollout and plugin doctor passed. Synthetic trace f79c5689bc915966fbd5f7fefc2b77fd was received and read back using the current v2 observations API: input contained only omitted/type/chars, userId empty. No model request or real conversation was used in this smoke test. Legacy trace read API returned HTTP 410; v2 observations succeeded. UI onboarding state was preserved privately on PVC across the rollout.

Create a free Langfuse project and enter its project keys using:

```sh
python3 /Users/karem/hermes-assistant/scripts/configure_langfuse.py
```

Default region EU; select --region us or jp to match the project. Keys are masked and verified against a fixed regional endpoint without redirects, then stored in hermes-langfuse. The gateway references this optional dedicated Secret; after changing keys restart the deployment, retain metadata capture, and verify a synthetic trace. Do not enable prompt, response, tool arguments/results or email capture.

## Monitoring
scripts/cluster_status.py exposes only fixed read-only Prometheus queries and alert metadata. Tested from the gateway against the existing monitoring service, without a Kubernetes service-account token or admin credentials. This helper limits its own requests, not the entire network. No automatic remediation or alerts schedule.

## WHMCS remote browser
Owner selected Kubernetes-only remote browsing and manual sign-in once per company. First company target: https://support.murabba.com/WMAA/supporttickets.php . No WHMCS API credentials, session cookies or login data collected. No ticket contents read or modified.

Browser is NOT deployed. A temporary non-root Pod using hostUsers:false, RuntimeDefault seccomp, dropped capabilities, read-only root, no volumes, secrets or service-account token completed on devops. libc.unshare(CLONE_NEWUSER) returned -1 / EPERM. The diagnostic Pod was deleted. Existing Hermes has the same restriction. This is a prerequisite test, not an actual Chromium launch.

Next engineering gate: design and review a dedicated browser worker with a compatible sandbox, its own company session PVC and authenticated interactive UI; validate it without credentials before owner sign-in. Keep mail/model/dashboard Secrets out of that worker. Do not use --no-sandbox, privileged mode, SYS_ADMIN, host PID/network or relax Hermes/Codex sandbox as an automatic workaround. Chromium requires an appropriate scoped seccomp/user namespace setup: https://playwright.dev/docs/docker . No node security changes made during this diagnostic.

## Groq and model routing
Owner enabled a Groq Free Plan key after resolving Groq's rejection of Python urllib's default User-Agent. Dedicated `hermes-jobs-groq` is used only by the jobs worker; only its GROQ_API_KEY is mirrored to `hermes-groq` for the main gateway, with explicit owner authorization. No Groq credential is injected into the dashboard. Both workers resolved the fixed Groq endpoint and returned READY on synthetic prompts; the jobs worker's native LangChain structured skill extraction also passed.

Main Hermes keeps its existing OpenRouter NVIDIA :free model as primary and exposes Groq / openai/gpt-oss-120b as a named provider and automatic fallback on provider failure. This is failover, not round-robin balancing. The owner explicitly revoked the blanket free-only requirement: the deployment renderer now accepts an explicitly selected paid OpenRouter model as well, while this deployment has not selected one. Existing primary free-model auxiliary restrictions remain appropriate to that primary; they are omitted for an explicitly selected paid primary. Groq remains subject to the account's plan and organization quotas; both components currently share that Groq quota. Keys and CV content remain outside Git.

## Scheduled job search and applications — 2026-10-27
Owner explicitly requested automatic search AND applications four times daily and removal of the 15-minute limit so each cycle finishes its current result set. Kubernetes CronJob hermes-jobs-schedule is active at 00:00, 06:00, 12:00 and 18:00 Africa/Cairo. It holds its Job open while the tracked run proceeds, forbids overlap, and skips an already active manual run. If a cycle spans the next scheduled slot, that slot is skipped rather than queued. No Codex desktop automation or local Mac scheduler was created.

Finish-search mode removes the former 15-minute, ten-submit-attempt, sixty-inspected-job and per-term result caps; run_non_stop stays false and repeat-page detection terminates a non-advancing search. Service quotas, platform limits, profile approval, manual authentication challenges, truthful answers, and visible submission confirmation remain required.

Acceptance: 45 offline tests, full pinned-upstream source compilation, Kubernetes server-side validation, rollout readiness, and a real isolated scheduler Job returning ready=true/started=false. That check used exactly the CronJob control credential and network identity and sent no applications. Browser/profile and model keys remain confined to the worker; the scheduler has no data volume or Kubernetes service-account token.
