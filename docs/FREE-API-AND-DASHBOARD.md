# Free cloud API and dashboard preparation

Owner requested a free cloud API on 26 October 2026; this supersedes the original subscription-only provider constraint. No local model is selected. OpenRouter's openrouter/free router selects only available free models and filters for required features. The published unfunded free tier normally permits 50 model requests per day and 20/minute; an agent turn can consume several requests. Quota is not unlimited and upstream availability may vary. See https://openrouter.ai/openrouter/free and https://openrouter.ai/docs/api_reference/limits . Do not add funds, payment methods or auto top-up for this setup.

Run locally (credential entry only, agent runtime stays on Kubernetes):

```sh
python3 /Users/karem/hermes-assistant/scripts/configure_free_api.py --dashboard
```

This verifies the key with the official key endpoint, refuses an account not reported as free-tier, then creates hermes-free-api. It optionally prompts for a new dashboard password twice (minimum 12 characters), derives the exact upstream scrypt hash inside the existing Kubernetes runtime (password on exec stdin only; no local scrypt dependency) and creates separate hermes-dashboard-auth. No password or API key is printed, written to a file or put in command arguments. Username: karem. Existing Telegram credentials are neither read nor changed. No inference call or active-provider change occurs in the helper.

config/deployment.free.example.json is the prepared target. Renderer accepts only openrouter/free or an explicit :free model for OpenRouter, adds only hermes-free-api to the gateway, and reduces max turns to five. No paid model fallback is configured. The actual model change requires verified Secrets and a Kubernetes rollout; this preparation alone is not evidence of a successful API call.

The optional dashboard is a separate container in the existing single gateway Pod. It gets only its dedicated dashboard-auth Secret, HOME/HERMES_HOME/TZ and the data-home mount needed to administer the requested profile, plus its own temporary volume. It does not mount the private-profile Secret or managed ConfigMap and does not inherit Telegram or model API environment variables. As an administrative interface it can access data in the managed profile, including stored credential state; protect its password accordingly. The non-loopback bind engages the native authentication gate, which refuses startup without an auth provider. Existing deny-ingress remains; no Service/Ingress/NodePort/public URL is created.

Reach it through an owner-authenticated Kubernetes tunnel once deployed:

```sh
kubectl --context kubernetes-admin@kubernetes -n hermes port-forward deployment/hermes 9119:9119 --address 127.0.0.1
```

Then open http://127.0.0.1:9119 and sign in. The dashboard and API runtime stay on Kubernetes. Configuration managed by bootstrap/GitOps is refreshed at startup; persist deployment/model choices in the repository to keep dashboard edits across rollouts. Credential rotation goes through Secrets. No cron jobs or deliveries are enabled by opening the dashboard.

A free model API changes inference only. It does not repair Codex CLI's Linux namespace sandbox incompatibility; that execution remains blocked without privilege expansion.

Credential-helper portability fix: the owner Mac Python lacks hashlib.scrypt. The helper now calls the installed dashboard hash_password function in the gateway Pod. A non-secret live fixture passed hash/verify and wrong-password rejection; 24 offline tests passed. Hashing failure stops before any Secret writes and does not print captured stdout/stderr.

## Public HTTPS access requested by owner

The owner requested access from anywhere and created A record hermes.murabba.net → 66.11.126.179. deploy/public-dashboard.json adds the Traefik HTTPS route, HTTP redirect, rate limiting, security headers and a letsencrypt-prod Certificate. The dashboard receives HERMES_DASHBOARD_PUBLIC_URL=https://hermes.murabba.net so origin/host validation and authentication use the declared address. The only Service is ClusterIP to dashboard port 9119; the gateway has no public listener.

Namespace deny-ingress remains. A narrow NetworkPolicy allows Traefik-labeled Pods in the traefik namespace to reach port 9119, and a separate solver-only rule allows HTTP-01 validation on port 8089. Native dashboard password authentication remains mandatory. This supersedes the original local-tunnel-only access design. Never bypass a browser certificate warning; wait for Certificate Ready and independently verify TLS, HTTP redirect and anonymous API denial before declaring public access complete.
