# Integration state — 2026-10-26

## Firecrawl
Built-in keyless Firecrawl selected for search and extraction. Public Kubernetes documentation search and scrape passed. No API key or paid provider configured for these tests. Keyless availability is upstream controlled.

## Kanban
Persistent boards: karem-work, karem-study, karem-personal. Existing current board preserved. Integration cards initially blocked; automatic dispatch, review dispatch, notification and subscription disabled in managed configuration. No scheduled jobs created.

## Langfuse
Official plugin version 2.0.0 pinned to NousResearch/hermes-official-plugins commit e1f16143f164c4db10ea8fc0fc47ff8ac611e9fc. Official installer resolved dependencies; doctor passed import and registration of 11 hooks. Capture explicitly set to metadata in the live private dotenv. Project credentials absent: no live trace delivery verified.

Create a free Langfuse project and enter its project keys using:

```sh
python3 /Users/karem/hermes-assistant/scripts/configure_langfuse.py
```

Default region EU; select --region us or jp to match the project. Keys are masked and verified against a fixed regional endpoint without redirects, then stored in hermes-langfuse. Secret creation alone does not activate gateway credentials: mount this dedicated Secret only in the gateway, retain metadata capture, and verify a synthetic trace before claiming delivery. Do not enable prompt, response, tool arguments/results or email capture.

## Monitoring
scripts/cluster_status.py exposes only fixed read-only Prometheus queries and alert metadata. Tested from the gateway against the existing monitoring service, without a Kubernetes service-account token or admin credentials. This helper limits its own requests, not the entire network. No automatic remediation or alerts schedule.

## WHMCS remote browser
Owner selected Kubernetes-only remote browsing and manual sign-in once per company. First company target: https://support.murabba.com/WMAA/supporttickets.php . No WHMCS API credentials, session cookies or login data collected. No ticket contents read or modified.

Browser is NOT deployed. A temporary non-root Pod using hostUsers:false, RuntimeDefault seccomp, dropped capabilities, read-only root, no volumes, secrets or service-account token completed on devops. libc.unshare(CLONE_NEWUSER) returned -1 / EPERM. The diagnostic Pod was deleted. Existing Hermes has the same restriction. This is a prerequisite test, not an actual Chromium launch.

Next engineering gate: design and review a dedicated browser worker with a compatible sandbox, its own company session PVC and authenticated interactive UI; validate it without credentials before owner sign-in. Keep mail/model/dashboard Secrets out of that worker. Do not use --no-sandbox, privileged mode, SYS_ADMIN, host PID/network or relax Hermes/Codex sandbox as an automatic workaround. Chromium requires an appropriate scoped seccomp/user namespace setup: https://playwright.dev/docs/docker . No node security changes made during this diagnostic.
