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

config/deployment.json and deploy/manifest.json use the final private GHCR image, openai-codex/gpt-6.1-sol, namespace hermes, Longhorn, the separate owner-profile Secret and optional namespace-only imagePullSecret hermes-registry. Deployment replicas remain zero pending credentials and runtime acceptance. No Service, Ingress, schedules, job applications, external messages or paid API calls enabled.

## Remaining gates

- Telegram bot token and positive numeric owner allowlist must be entered locally using scripts/configure_telegram.py; never paste the token into chat.
- Owner allowlist rejection, gateway persistence across restart and a full protected backup/restore remain unverified. Longhorn backup target is available, but CSI VolumeSnapshot APIs are absent.
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
