# Independent GitOps repository

Source: https://github.com/egyhaty/hermes-assistant (private). Do not add Hermes files to karm-devops. The existing Kubernetes cluster is reused only as the runtime platform.

Argo uses a repository-specific read-only SSH deploy key, stored only in its hermes-repository Secret. The foundation Application is manual-sync, pinned to an exact commit, without a deletion finalizer. It owns the restricted namespace, retained Longhorn PVC and deny-ingress policy. Do not delete the PVC when moving application paths.

Render the final gateway manifests under deploy only after choosing an available subscription model and immutable runtime image. Keep the gateway at zero replicas until Telegram owner allowlist, owner OAuth and live acceptance are ready. Keep credentials outside git; profile is a separate mounted Secret. No automated scheduling or paid provider fallback is enabled.

The initial integration PR in karm-devops was closed and its remote branch deleted at the owner's request. All current source and future image builds belong to this repository.
