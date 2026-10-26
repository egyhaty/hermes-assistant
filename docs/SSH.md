# SSH credentials for the gateway

The owner explicitly authorized importing all private keys from ~/.ssh on 2026-10-26. scripts/configure_ssh.py transfers private-key files plus existing trusted host fingerprints directly to Secret/hermes-ssh via kubectl stdin. It does not print key material or copy the local SSH config. No key material is committed, put on the shared data PVC, or injected into dashboard.

Gateway mount: /etc/hermes-ssh, read-only, Secret file mode 0440, root-owned and readable through runtime fsGroup 10000. HERMES_SSH_CONFIG=/etc/hermes-ssh/config. Secret updates are projected automatically; adding the volume initially requires a rollout.

Select a key explicitly:

```sh
ssh -F /etc/hermes-ssh/config -i /etc/hermes-ssh/id_ed25519 USER@HOST 'uptime; cat /proc/loadavg'
```

The dedicated config enables BatchMode, IdentitiesOnly, strict host key checks, disables forwarding, uses the imported known_hosts files and limits connection setup time. IdentityFile none suppresses default identity discovery: pass -i for the selected key. Other imported filenames are available in the same directory. Unknown or changed host keys must be independently verified before updating trusted fingerprints; do not disable checking. Encrypted identities require a separate approved unlock flow and were not decrypted. SSH agent sessions, macOS Keychain secrets and passphrases were not copied.

Possession of these keys grants their actual remote account permissions. There is no server-enforced read-only restriction introduced by this mount. Read-only inspection is the operating default; production writes and outbound communications need explicit owner authorization. Do not read, print, upload, or include key contents in prompts, logs, tracing, tickets or repositories.
