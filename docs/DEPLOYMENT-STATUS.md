# Deployment status — 26 October 2026

Source: independent private repository https://github.com/egyhaty/hermes-assistant . Local checkout: /Users/karem/hermes-assistant . The temporary karm-devops PR was closed, its branch removed and its original unrelated working changes preserved. No Hermes/Codex agent is installed on the Mac.

## Verified

- Existing context kubernetes-admin@kubernetes: three Ready amd64 nodes, Kubernetes v1.36.5, Cilium.
- Manual Argo foundation is Synced/Healthy from the independent repository using a repository-specific read-only SSH deploy key. No app-of-apps integration or automatic sync enabled.
- hermes-data: Bound, 20Gi Longhorn PVC, Retain StorageClass, three configured replicas; attached/healthy during the runtime test. Argo prune/delete protection is retained in final manifests.
- Initial Kubernetes runtime test: UID 10000, read-only root filesystem (write attempt returned EROFS), no mounted service-account token, no baked profile. Codex 0.164.0 was executable. A SQLite probe row survived pod recreation. This does not claim authenticated gateway memory acceptance.
- Owner device-code sign-in was enabled at the owner's request. Hermes OAuth login succeeded on the PVC and auth status was logged in. Account catalog includes gpt-6.1-sol; this model is selected. No paid API credentials or fallback provider configured.
- Final selected immutable image and successful security result: docs/build-receipts/clean-image.json and security-result.json. Zero patchable HIGH/CRITICAL findings, no scanner exceptions. This is not a complete audit or a claim of zero vulnerabilities of every severity.
- 20 offline tests and structural validation passed. Full stopped manifest passed real server-side dry-run.

## Desired deployment

config/deployment.json and deploy/manifest.json use the final private GHCR image, openai-codex/gpt-6.1-sol, namespace hermes, Longhorn, the separate owner-profile Secret and optional namespace-only imagePullSecret hermes-registry. Kustomize activates exactly one replica after the checks recorded below; the renderer retains its safe zero-replica default. No Service, Ingress, schedules, job applications, external messages or paid API calls enabled.

## Remaining gates

- Owner onboarding completed; no further token entry is needed.
- Owner-originated Telegram message/response acceptance passed: the owner sent the requested Arabic test and confirmed receipt of جاهز. Native adapter owner/non-owner admission and encrypted in-cluster restore also passed. Off-cluster disaster recovery/key recovery remains unverified.
- Codex `sandbox linux -- /bin/true` failed: bwrap cannot create a new namespace under the restricted pod. Execution remains blocked; no privilege expansion or sandbox bypass was used. A separately reviewed compatible worker is needed.

## Private image and volume ownership verification

The dedicated hermes-registry Secret was entered by the owner and the final private GHCR image was pulled successfully by Kubernetes. Its runtime reports UID 10000, Hermes metadata 0.22.5, msgpack 1.2.1, urllib3 2.8.0 and brotlicffi 1.2.1.0. Subscription auth remained logged in after changing images.

The first model attempt was rejected before sending because the PVC mount root belonged to UID 0. With no active writer, all 21 owner-created entries were moved by UID 10000 into hermes-home on the same PVC. The runtime now mounts that owned directory via subPath; a restricted non-root initContainer creates/verifies it on fresh volumes and refuses unattended legacy-root migration. No chown/root init or privilege change was used. The test row and OAuth login survived recreation. The final-image native CLI returned exactly K8S_SUBSCRIPTION_OK using openai-codex/gpt-6.1-sol (one subscription model call). Telegram remains unconfigured and the Deployment remains stopped.

## Telegram owner onboarding

Create a dedicated bot with the official https://t.me/BotFather using /newbot. Keep its token private. Run locally:

```sh
python3 /Users/karem/hermes-assistant/scripts/configure_telegram.py
```

The helper masks token input, verifies the bot, refuses an existing webhook, and prints a unique Start link. Open that link in the owner Telegram account and press Start. Only the matching private message identifies the numeric owner; forwarded, group, bot and unrelated messages cannot enroll. The helper creates hermes-credentials directly through stdin and leaves the Deployment at zero replicas. It sends no bot messages. Do not paste credentials into chat.

## Telegram and restore acceptance — 26 October

Owner onboarding completed: hermes-credentials contains the two required Telegram keys; getMe verified the token and getWebhookInfo found no webhook. Native TelegramAdapter intake accepted the configured owner and rejected a different synthetic user without any messages sent. Full stopped data-home was archived with AES-256-GCM on hermes-backup, restored onto hermes-restore-check and compared: 551 entries matched; five SQLite databases passed integrity_check. Receipt: docs/build-receipts/restore-result.json. This is an in-cluster restore test; no off-cluster disaster recovery or key recovery has been demonstrated. The effective runtime policy was verified as ignore after fresh ConfigMap loading and plugin discovery. The gateway was activated with a single replica. A SQLite marker survived transition to the real Deployment. A second rollout exposed that /usr/bin/tini dispatches to s6 and is incompatible with this restricted non-root startup. It was reverted to the verified bootstrap. The PID1 child-reaping warning remains a runtime limitation; no privileges were expanded. Process readiness alone does not prove a Telegram reply.

## Live Telegram acceptance completed

The final running single-replica gateway connected in polling mode. After its restart, the SQLite marker persisted. On 26 October the owner sent the Arabic exact-response test; the gateway used openai-codex/gpt-6.1-sol, completed one API call in the recorded turn, and sent the four-character response. The owner confirmed receipt of جاهز. Argo reports Synced/Healthy with successful manual sync. No model API key or paid fallback was introduced. Telegram home-channel onboarding is optional; /sethome selects a destination but does not register a schedule. No cron jobs or cross-platform deliveries have been configured.

## Free API and authenticated dashboard activated — 26 October

At the owner request, the active provider is now OpenRouter with model openrouter/free. A native Hermes CLI one-shot returned FREE_API_OK (exit 0) using this provider; no paid fallback_model is configured. Free-tier API credentials and dashboard scrypt/signing credentials are stored in separate Secrets. The gateway has the API key; dashboard env contains only its own login Secret. Dashboard has no Telegram credential env or private-profile Secret mount; its data-home mount is administrative access to the managed profile.

The dashboard started from packaged assets on port 9119 with the native auth gate enabled. An anonymous /api/config request returned HTTP 401 and the browser displayed Sign in — Hermes Agent with PUBLIC BIND · AUTH REQUIRED. It is reached only through an owner-local Kubernetes port-forward, currently http://127.0.0.1:19119 . No Service/Ingress/NodePort was created and namespace ingress deny remains. The tunnel is session-bound and must be restarted after a Pod rollout or local terminal exit. This does not claim off-cluster dashboard availability or successful owner login before confirmation. Codex sandbox execution remains separately blocked.

## Public dashboard rollout in progress

Owner explicitly requested permanent anywhere access and added hermes.murabba.net → 66.11.126.179. Public DNS resolvers return the correct IP. HTTPS ingress, redirect, authentication/public_url declaration, rate limit and narrowly scoped ingress rules were applied; the certificate is Ready. Public and authoritative DNS resolve correctly. TLS chain/hostname verification passed against the published IP, HTTPS root redirects to login (302), anonymous /api/config is denied (401), and HTTP redirects to HTTPS (301). The local Mac resolver still caches a negative DNS result, so public browser login from that machine remains pending cache propagation. Receipt: docs/build-receipts/public-dashboard-acceptance.json.

## Gmail configuration repaired — 26 October

Himalaya v2.2.1 on the PVC now uses the v2 IMAP/TLS account schema rather than the unsupported legacy backend.gmail table. The owner entered a Google app password through configure_gmail.py into hermes-gmail; only the gateway receives the read-only Secret mount. Native account check authenticated successfully: imap ok=true, exit 0. No email content was read or sent. Runtime private config and password-command helper persist on the data PVC. See docs/GMAIL-HIMALAYA.md.
