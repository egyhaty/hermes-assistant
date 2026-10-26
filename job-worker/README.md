# Kubernetes Easy Apply worker

Selected upstream: GodsScion/Auto_job_applier_linkedIn, MIT, immutable revision in upstream.json. Chosen for its focused Easy Apply flow, straightforward control panel and current unanswered-question guards. The alternative Ultimate adds broader external-application/networking behavior and explicit sandbox-disabling launch flags, increasing the review surface.

This adapter runs ordinary Selenium against an existing sandboxed Chromium session. It does not use UC stealth patches, auto-download drivers, disable Chromium's sandbox or bypass CAPTCHA. No real LinkedIn login, form fill or application has been tested yet.

## Credentials and UI

Worker receives only hermes-jobs-auth (existing UI username/password verifier plus dedicated control token), hermes-free-api and optional hermes-jobs-profile (owner CV/facts). It never mounts production SSH, mail, Hermes profile/data or Telegram Secrets and has no Kubernetes service-account token.

Planned authenticated UI: https://hermes.murabba.net/jobs/ . Browser sign-in is manual, in the private noVNC desktop. VNC, CDP and the upstream unauthenticated Flask panel listen only on Pod loopback. The aiohttp gateway authenticates both HTTP and WebSocket requests and checks browser POST Origin. The upstream self-updater is denied: images update through CI.

No application runs on startup. Complete truthful profile and sign in first, then run automatic Easy Apply. Maximum ten successful submissions per run, with existing CSV history for deduplication. Missing required answers are skipped; no recruiters/messages/connections or recurring schedule enabled. Models must explicitly end in :free. AI is off until configured. The owner has authorized automatic applications; setup is not a per-application approval gate.

CV remains in a private Kubernetes Secret/data volume, never Git. configure_profile.py imports it with verified JSON facts; configure_auth.py copies only the existing UI password verifier, not its signing key. These commands were prepared but have not yet been run.

## Security activation gate — blocked by automatic approval review

Current RuntimeDefault profile denies unshare(CLONE_NEWUSER), including in a hostUsers:false diagnostic. No compatible browser runtime is currently verified. Prepared files:

- security/seccomp.json: translated from the official Playwright Docker seccomp sample, resolving Docker-specific capability/architecture conditions for amd64 with zero host capabilities. Default deny retained; Chromium namespace calls allowed.
- security/apparmor: named hermes-jobs-browser profile with userns permission and kernel-control filesystem write denials. Container drops all host capabilities and retains read-only root/no privilege escalation.
- render.py: stopped Deployment, dedicated 5Gi PVC, Localhost security profiles, fixed devops node, authenticated ingress, DNS/HTTPS-only egress with cluster/private/node networks excluded.

The attempted installation of only /etc/apparmor.d/hermes-jobs-browser and /var/lib/kubelet/seccomp/hermes-jobs-browser.json on devops (66.11.126.178), with apparmor_parser reload of that named profile, was rejected before execution by automatic approval review. Reason: persistent root-owned host AppArmor/seccomp changes and user namespace allowances exceed clear authorization in the general worker-install request. No host profile, sysctl, daemon config or existing workload security was changed. Do not work around the rejection by using another transport, privileged installer or --no-sandbox. Obtain explicit owner authorization for the concrete named-node change before retrying.

After authorization, validate parser, install only these named profiles, run a no-secret namespace test, then real Chromium chrome://sandbox acceptance. Activate only a scanned immutable image, verify UI auth/anonymous denial and WebSocket access, then request owner manual LinkedIn sign-in. Until these gates pass keep replicas=0 and do not claim a functioning remote browser or applications sent.
