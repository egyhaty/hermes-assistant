# Self-hosted job search and applications

The jobs workspace, persistent Chromium sessions, application queue, evidence and reports run on the owner's Kubernetes servers. GPT matching uses the official Codex client on a separate private worker, signed in with the owner's ChatGPT account. Model inference uses OpenAI; no GPU is required on these servers. The Mac and this chat do not need to stay open for the server schedule.

## Connect and start

Open `/jobs/gpt/` from the authenticated jobs workspace. Start sign-in, open the official `https://auth.openai.com/codex/device` page and complete the device-code flow yourself. Access and refresh credentials remain only in the matcher's separate persistent directory. They are never copied to the browser worker or sent in dashboard responses.

After sign-in, eight synthetic fit checks run automatically against the approved professional profile. They cover a core Linux role, supervised basic cloud support, unsupported AI/backend requirements, mandatory production cloud tenure, Emirati-only jobs, conflicting countries, mandatory banking/payments expertise and mandatory technical degrees. No applications are submitted by validation. All eight must pass before the first application cycle starts automatically. A failed check holds submissions and exposes the result for review; it does not select another model/provider.

The owner-selected server schedule is **daily at 08:00 Asia/Dubai**. Kubernetes forbids overlapping scheduled runs. Manual and scheduled starts share the same control lock and persistent application journal. A disconnected GPT account or unfinished validation skips a scheduled submission cycle with a visible reason.

The currently validated automatic submission adapter is **NaukriGulf Easy Apply**. LinkedIn, Indeed, Bayt and GulfTalent account connections and discovery are distinct from submission-adapter readiness. Do not represent those four as enabled automatic submission paths.

## GPT boundary

`JOB_SCREENING_MODE=codex` selects the private matcher. `JOB_SCREENING_SHARING_APPROVED=1` records the owner's authorization to send the professional summary, skills, projects, employment titles/dates and education. Phone/email, residency and work-permit answers are excluded. The PDF, browser cookies and application screenshots are not sent for matching.

The matcher runs `gpt-6.2-sol` at low reasoning effort through the pinned official Codex client bundle. Its subprocess uses a separate authentication directory and does not inherit other server credentials. Command execution, web search, connected apps, MCP servers and multi-agent tools are disabled. The sandbox stays read-only; ephemeral runs return one schema-validated decision. Unexpected tool use, incomplete output, connection errors or unknown mandatory requirements hold the job without a submission. The browser worker keeps its existing sandbox and resource isolation.

Local matching and separately consent-gated API implementations remain available in code for explicit configuration. The server deployment selects Codex; there is no automatic fallback to Groq or rule-based submission. The legacy Start action is refused in this mode. Profile approval and CV identity are rechecked before submission.

## Submission and recovery

`/data/job-applications.sqlite3` records reviews, CV hashes, attempts, platform evidence and run outcomes. An atomic claim is written before the first Easy Apply click. A success message must agree with Already Applied on a fresh copy of the original listing. Screenshots of this persisted state stay under the worker's private evidence directory when capture succeeds. Text confirmation is retained even if image capture fails.

An uncertain/interrupted attempt is never retried automatically. Startup, after the exclusive worker lock, marks interrupted runs and attempts accordingly. A newly selected GPT matcher can reconsider an unattempted rules-based rejection; confirmed, uncertain and form-held attempts are never reopened by that process. Further forms receive no guessed answers or additional Submit click. MFA, CAPTCHA, new agreements and unknown salary/work-authorization answers are held for owner action.

The early rules-based flow sent three confirmed applications. Two later audits found mandatory AI/backend or banking/payments experience not established in the CV. Those real submissions and audit warnings remain in the journal and reports. They must not be represented as verified matches or removed from counts. Rules-based automatic submission was paused before preparing GPT matching.

## Reports

`/jobs/reports/` provides Dubai-time daily outcomes and recent server runs. Authenticated application and run CSV exports, per-run operational logs and captured platform evidence are available there/in application activity. Discovery is never counted as a submission. Screening-audit warnings remain visible next to confirmed totals. Exported untrusted text is neutralized against spreadsheet formulas. Reports and model setup require the owner's jobs session; mutations also require the expected Origin.

## Deploy and verify

`deploy/jobs-gpt.json` adds a private singleton matcher with a separate PVC subdirectory, restricted non-root containers, no Kubernetes service-account token, and ingress only from the jobs worker. The browser receives a separate internal matcher-control token, not ChatGPT credentials. No public matcher Ingress is created. Source manifests retain zero replicas/suspended install defaults; live activation is intentional and separate from a whole-foundation sync.

The jobs image installs the official native Codex 0.171.0 bundle, including its companion host, from the OpenAI npm release after verifying its pinned SHA-512 integrity. The image build checks the binary, compiles source, runs the job tests and scans for fixable HIGH/CRITICAL vulnerabilities. Offline tests verify auth gates, data minimization, duplicate protection, recovery and truthful reporting. Verify the real GPT connection and all eight fit checks before activation.

Official references: [Sign in with ChatGPT](https://learn.chatgpt.com/docs/sign-in-with-chatgpt), [Codex configuration](https://learn.chatgpt.com/docs/config-file/config-reference), [model selection](https://developers.openai.com/api/docs/guides/model-selection).

The original 0.164.0 client rejected GPT-6.2 Sol. A synthetic matching request using the same owner's connection succeeded with client 0.171.0 and GPT-6.2 Sol. Readiness is bound to the current model, fit-check revision, profile and resume; changing them requires fresh validation. Existing rejected-role rechecks remain limited to unattempted records.
