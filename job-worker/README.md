# Kubernetes Easy Apply worker

Selected upstream: GodsScion/Auto_job_applier_linkedIn, MIT, immutable revision in upstream.json. Chosen for its focused Easy Apply flow, straightforward control panel and current unanswered-question guards. The alternative Ultimate adds broader external-application/networking behavior and explicit sandbox-disabling launch flags, increasing the review surface.

This adapter runs ordinary Selenium against an existing sandboxed Chromium session. It does not use UC stealth patches, auto-download drivers, disable Chromium's sandbox or bypass CAPTCHA. No real LinkedIn login, form fill or application has been tested yet.

## Credentials and UI

Worker receives only hermes-jobs-auth (existing UI username/password verifier plus dedicated control token), hermes-free-api and optional hermes-jobs-profile (owner CV/facts). It never mounts production SSH, mail, the full Hermes home/profile, or Telegram Secrets and has no Kubernetes service-account token.

Planned authenticated UI: https://hermes.murabba.net/jobs/ . Browser sign-in is manual, in the private noVNC desktop. VNC, CDP and the upstream unauthenticated Flask panel listen only on Pod loopback. The aiohttp gateway uses an ordinary password form with six-hour in-memory Secure/HttpOnly/SameSite=Strict sessions for HTTP and WebSocket requests, plus browser POST/WS Origin checks and failed-login throttling. It uses the existing owner UI password verifier; no signing key is copied. Native HTTP Basic was replaced after the embedded browser failed to display its prompt. The upstream self-updater is denied: images update through CI.

No application runs on startup. Complete truthful profile and sign in first, then run automatic Easy Apply. Maximum ten successful submissions per run, with existing CSV history for deduplication. Missing required answers are skipped; no recruiters/messages/connections or recurring schedule enabled. Models must explicitly end in :free. AI is off until configured. The owner has authorized automatic applications; setup is not a per-application approval gate.

CV remains in a private Kubernetes Secret/data volume, never Git. configure_profile.py imports it with verified JSON facts; configure_auth.py copies only the existing UI password verifier, not its signing key. Both provisioning helpers were run. Current owner facts are in Kubernetes Secrets, not Git. Total career years must not be treated as per-skill cloud production experience; unknown work-permit answers stay blank.

## Security activation history and current verification

Current RuntimeDefault profile denies unshare(CLONE_NEWUSER), including in a hostUsers:false diagnostic. No compatible browser runtime is currently verified. Prepared files:

- security/seccomp.json: translated from the official Playwright Docker seccomp sample, resolving Docker-specific capability/architecture conditions for amd64 with zero host capabilities. Default deny retained; Chromium namespace calls allowed.
- security/apparmor: named hermes-jobs-browser profile with userns permission and kernel-control filesystem write denials. Container drops all host capabilities and retains read-only root/no privilege escalation.
- render.py: stopped Deployment, confined persistent subPath, Localhost security profiles, fixed devops node, authenticated ingress, DNS/HTTPS-only egress with cluster/private/node networks excluded.

The attempted installation of only /etc/apparmor.d/hermes-jobs-browser and /var/lib/kubelet/seccomp/hermes-jobs-browser.json on devops (66.11.126.178), with apparmor_parser reload of that named profile, was rejected before execution by automatic approval review. Reason: persistent root-owned host AppArmor/seccomp changes and user namespace allowances exceed clear authorization in the general worker-install request. No host profile, sysctl, daemon config or existing workload security was changed. Do not work around the rejection by using another transport, privileged installer or --no-sandbox. The owner subsequently explicitly approved the two named files, then separately approved openat2/chroot and clone3 ENOSYS compatibility changes. Those exact worker-only profiles were applied on devops; no global sysctl or existing Hermes profile changed. The namespace smoke test returned 0/errno 0.

Real chrome://sandbox inspection reported Namespace layer 1, PID/network namespaces and Seccomp-BPF/TSYNC enabled, with adequately sandboxed status. Authenticated desktop RFB/WebSocket and panel proxy passed using synthetic credentials in a private test server. Browser state-marker and CDP readiness survived a real rollout restart. Owner manual LinkedIn login and first application acceptance remain pending. No applications have been sent.

## Storage and run limits

Longhorn refused the new 5Gi PVC because its provisioned-capacity reservations were exhausted, despite free physical space. No overprovisioning policy or old volumes were changed/deleted. Worker uses only subPath hermes-home/job-worker-data on the existing hermes-data PVC, pinned to the same node. It cannot traverse to the rest of the mounted Hermes home. The gateway can administer this subdirectory. A kernel flock prevents two worker processes owning the profile, a stable hostname and stale-singleton-link cleanup make rollouts safe. Cookies and login databases are not read or rewritten by that cleanup. The failed newly created zero-data detached volume was verified unused and removed. This is directory isolation on shared storage, not a separate physical volume or quota.

Hard submission count cap is ten successes. Between jobs the worker also stops after 60 inspections or 900 seconds; this is not a process wall-clock kill. No recurring schedule is installed. AI is initially off; if enabled it is restricted to an explicit :free OpenRouter model.

Xvfb authentication: startup creates a mode-0600 Xauthority file with a fresh MIT-MAGIC-COOKIE-1 entry, exports XAUTHORITY to every GUI child, and starts the local-only X server with -auth. This prevents PyAutoGUI/Xlib startup failures without disabling X authentication. Jobs ingress uses Referrer-Policy: same-origin so browser form submissions retain the correct Origin; cross-origin and null-Origin mutations remain denied.
