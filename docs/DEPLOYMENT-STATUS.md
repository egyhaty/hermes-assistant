# Deployment status — 26 October 2026

Source: independent private repository https://github.com/egyhaty/hermes-assistant . Local checkout: /Users/karem/hermes-assistant . The temporary karm-devops PR was closed, its branch removed and its original unrelated working changes preserved. No Hermes/Codex agent is installed on the Mac.

## Verified

- Existing context kubernetes-admin@kubernetes: three Ready amd64 nodes, Kubernetes v1.36.5, Cilium.
- Manual Argo foundation is Synced/Healthy from the independent repository using a repository-specific read-only SSH deploy key. No app-of-apps integration or automatic sync enabled.
- hermes-data: Bound, 20Gi Longhorn PVC, Retain StorageClass, three configured replicas; attached/healthy during the runtime test. Argo prune/delete protection is retained in final manifests.
- Initial Kubernetes runtime test: UID 10000, read-only root filesystem (write attempt returned EROFS), no mounted service-account token, no baked profile. Codex 0.164.0 was executable. A SQLite probe row survived pod recreation. This does not claim authenticated gateway memory acceptance.
- Owner device-code sign-in was enabled at the owner's request. Hermes OAuth login succeeded on the PVC and auth status was logged in. Account catalog includes gpt-6.1-sol; this model is selected. No paid API credentials or fallback provider configured.
- Final selected immutable image and successful security result: docs/build-receipts/clean-image.json and security-result.json. Zero patchable HIGH/CRITICAL findings, no scanner exceptions. This is not a complete audit or a claim of zero vulnerabilities of every severity.
- 18 offline tests and structural validation passed. Full stopped manifest passed real server-side dry-run.

## Desired deployment

config/deployment.json and deploy/manifest.json use the final private GHCR image, openai-codex/gpt-6.1-sol, namespace hermes, Longhorn, the separate owner-profile Secret and optional namespace-only imagePullSecret hermes-registry. Deployment replicas remain zero pending credentials and runtime acceptance. No Service, Ingress, schedules, job applications, external messages or paid API calls enabled.

## Remaining gates

- Dedicated read:packages credential must be entered locally using scripts/configure_registry.py; never paste it into chat.
- Telegram bot token and positive numeric owner allowlist must be entered locally using scripts/configure_telegram.py; never paste the token into chat.
- Final patched image startup, a subscription model response, owner allowlist rejection, gateway persistence across restart and a full protected backup/restore remain unverified. Longhorn backup target is available, but CSI VolumeSnapshot APIs are absent.
- Codex `sandbox linux -- /bin/true` failed: bwrap cannot create a new namespace under the restricted pod. Execution remains blocked; no privilege expansion or sandbox bypass was used. A separately reviewed compatible worker is needed.
