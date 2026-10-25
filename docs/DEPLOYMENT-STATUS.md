# Deployment status — 25 October 2026

Existing cluster context: `kubernetes-admin@kubernetes`; three Ready amd64 nodes, Kubernetes v1.36.5, Cilium. No Hermes/Codex agent was installed on the Mac.

Manual Argo Application `hermes-foundation`, pinned to fa89e50b2cf830b14e41d9d53a7f35668a0717c9, is Synced/Healthy. Namespace `hermes` enforces restricted pod security. `hermes-data` is Bound, 20Gi, Longhorn, three replicas configured, Retain StorageClass. Argo prune/delete protection is set on the PVC. The foundation has no gateway Deployment, Service, Ingress or credentials.

Longhorn backup target reports available. CSI VolumeSnapshot resources are absent; backup/restore has not been tested for this PVC.

Official base image amd64 digest and source revision are recorded in container/versions.json. Upstream Docker Build, Test, and Publish run https://github.com/NousResearch/hermes-agent/actions/runs/37436680662 succeeded for that revision. Registry digest and OCI revision were checked; signature verification has not been performed.

18 offline tests and structural validation passed. Foundation server admission dry-run passed after namespace creation. The first custom image build found an actual npm-prefix incompatibility; Dockerfile now installs Codex with an explicit /usr/local prefix. Corrected build: https://github.com/egyhaty/karm-devops/actions/runs/40230367057 . Runtime inspection pending.

Owner selected ChatGPT subscription authentication via openai-codex, with no paid API or fallback. No paid requests made, Telegram poller enabled, schedules registered or external messages sent. Available subscription model and owner OAuth login, Telegram bot token and positive numeric owner allowlist, separate Codex login, container startup, sandbox acceptance and backup/restore remain activation gates.

Source moved to independent private repository https://github.com/egyhaty/hermes-assistant . Prior karm-devops PR #37 was closed, branch removed, and original working tree restored to its prior unrelated modifications. Argo now reads the independent repository. Private owner profile is stored in hermes-profile Secret only.

## Runtime evidence

The Docker Hub custom image in docs/build-receipts/runtime-tested-image.json ran on Kubernetes as UID 10000 with a read-only root, no service-account token and no baked private profile. Codex reports 0.164.0. SQLite persisted one probe row after pod recreation; Longhorn reports attached/healthy. This checks SQLite persistence, not an authenticated gateway memory conversation.

Codex sandbox attempt failed: `bwrap: No permissions to create a new namespace`. Execution remains blocked; no privilege escalation, seccomp relaxation or sandbox bypass was used. A separately reviewed compatible worker is needed before enabling execution.

The independent repository build succeeded: https://github.com/egyhaty/hermes-assistant/actions/runs/40230687787 . Its GHCR digest is recorded separately. Subscription OAuth login is awaiting owner approval. No gateway/poller is active.
