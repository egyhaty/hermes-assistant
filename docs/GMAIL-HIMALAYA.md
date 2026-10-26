# Gmail with Himalaya v2.2.1

The owner-installed binary is /opt/data/cache/scratch/bin/himalaya, version 2.2.1, revision 5b12b2a8c2c253b98f15c46610ad74cba2a182bc. All commands run on Kubernetes. The private runtime configuration is /opt/data/workspace/himalaya-config/config.toml, mode 0600; HIMALAYA_CONFIG selects it in the gateway environment.

Root cause: the old [accounts.gmail.backend.gmail] table is not the v2 backend schema. Native Gmail REST also takes OAuth bearer tokens, not Google app passwords. For the owner's existing app-password method, use the v2 IMAP block with TLS:

```toml
[accounts.gmail]
default = true
email = "YOUR_ADDRESS@gmail.com"

[accounts.gmail.imap]
server = "imaps://imap.gmail.com:993"

[accounts.gmail.imap.sasl.plain]
username = "YOUR_ADDRESS@gmail.com"
password.command = ["/opt/hermes/.venv/bin/python", "/opt/data/workspace/himalaya-config/read_password.py"]
```

The private read_password.py helper reads /etc/hermes-mail/HIMALAYA_APP_PASS and emits it only to the Himalaya credential subprocess. Never invoke it directly or log its output. The fallback temporary environment variable is not durable across processes/restarts. The gateway mounts the dedicated hermes-gmail Secret read-only with mode 0440/fsGroup; dashboard does not mount it. Admins and the same-UID administrative dashboard can access shared profile data, so this does not isolate secrets from a compromised administrative account.

Enter/rotate credentials without putting them in chat, shell history, arguments or files:

```sh
python3 /Users/karem/hermes-assistant/scripts/configure_gmail.py
```

The helper accepts a 16-character Google app password, strips display spaces and sends it only to the Kubernetes API via stdin. The optional projected Secret updates automatically; allow kubelet projection time after rotation. Do not use the normal Google account password.

Verified on 26 October 2026: account list reports an IMAP backend; account check with the actual projected Secret returned {"account":"gmail","backends":[{"backend":"imap","ok":true,"error":null}]} and exit code 0. This checks handshake/authentication without reading messages. No SMTP/send backend or mail schedule was configured, and no messages were read/sent by this repair.

Use v2 commands and flags: --json (not -o json), mailbox (not folder), and -m/--mailbox for mailbox selection. Reading message content, marking messages, deleting and sending are separate actions requiring the owner's corresponding instruction. A Google app password itself is not read-only access; application procedure limits this repair to account checks.

Sources pinned to the installed version:
- https://raw.githubusercontent.com/pimalaya/himalaya/v2.2.1/config.sample.toml
- https://raw.githubusercontent.com/pimalaya/himalaya/v2.2.1/MIGRATION.md
