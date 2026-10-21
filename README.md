# Urumi MCP Gateway

An original MCP gateway/control plane: one MCP endpoint federating multiple MCP servers, with per-user API keys, role and tool permissions, audit logging, failure isolation, an admin dashboard, and a tool-calling chat agent. The deployment target is one Helm chart for local k3d and production-like k3s.

```
Dashboard / Chat / Cursor / MCP Inspector → ONE GATEWAY URL (/mcp) → woocommerce | weather | currency MCP servers
                                                   │                          └→ WooCommerce REST → WordPress → MySQL(PVC)
                                                   └→ PostgreSQL (users, keys, invitations, servers, audit)
```

## Layout
- services/gateway: FastAPI gateway, MCP server/client, admin API, chat and audit
- services/woo-mcp: WooCommerce MCP with product/order/customer tools
- services/weather-mcp and services/currency-mcp: additional upstream MCPs
- dashboard: React + TypeScript + Vite
- infrastructure/helm/urumi: one chart with local and production values
- docs: architecture, threat model, MCP flow, demo script, status and assessment gap matrix

## Windows clone and local setup

On another Windows computer, clone the repository and inspect its state before
making changes:

```powershell
git clone https://github.com/MananBhutada/urumi-mcp-gateway.git
Set-Location .\urumi-mcp-gateway
git status --short
```

Install Python 3.12, Node.js 22, Docker Desktop, kubectl, Helm, and k3d for the
full local-cluster workflow. Create a Python environment and install test
dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r services\gateway\requirements.txt
python -m pip install -r services\woo-mcp\requirements.txt
python -m pip install pytest
Set-Location .\dashboard
npm ci
Set-Location ..
```

These are setup instructions, not a claim that a fresh clone or clean cluster
was tested in the latest verification. The exact tests observed for the current
working tree are recorded in [docs/STATUS.md](docs/STATUS.md).

## Quick start (disposable local cluster)

Set `LLM_API_KEY` in the protected environment used to launch the script if
chat should be enabled; without it, chat returns a configuration error. The
script stages this value in a permission-restricted temporary file and removes
that file on exit. Helm still stores chart values in release data, so this
workflow is only for a disposable local cluster.
Before using an existing `k3d-urumi` cluster, the script checks its context
and release and requires an interactive typed confirmation; it refuses a
non-interactive existing-release upgrade. This is not a substitute for
reviewing a redacted plan. Do not target a shared cluster or the existing
revision-7 release without separately reviewing the proposed changes.

```bash
./scripts/dev.sh
```

On Windows, add `127.0.0.1 store.urumi.local dashboard.urumi.local` to
`C:\Windows\System32\drivers\etc\hosts` using an elevated editor.
The local-only bootstrap admin key is set in infrastructure/helm/urumi/values-local.yaml under secrets.bootstrapAdminKey. It is a disposable demo credential and must never be reused in production.

MCP client config (Cursor / Inspector): URL `http://dashboard.urumi.local/mcp`, header `Authorization: Bearer <Urumi Gateway API key>`. Do not use an LLM-provider key for Gateway sign-in or MCP authentication.

## Production values
Use values-prod.yaml and provide unique secrets through a secret manager or deployment-time secret injection. The production gateway refuses to start with a weak gateway secret, a weak bootstrap admin key, or SQLite. Do not commit real credentials or a populated production values file.

Bootstrap-key recovery is disabled by default. Because API-key records do not
identify which key originally bootstrapped an admin, recovery must be explicitly
enabled with Helm value `bootstrapAdminKeyRecovery: true` after setting the
intended bootstrap key through the approved secret path. Startup then adds that
key to the existing ADMIN account only if its hash is not already assigned;
other keys are not revoked. Verify sign-in, then disable the recovery value.
The PostgreSQL transaction advisory lock serializes this operation across
Gateway replicas.

## Chat model provider
The chat layer uses an OpenAI-compatible chat-completions API. Configure `LLM_BASE_URL` (provider base URL, such as `https://openrouter.ai/api/v1`), `LLM_MODEL` (the provider's exact model identifier), and `LLM_API_KEY`. The selected provider and model must support function/tool calling. These settings have empty defaults, so chat stays unavailable until all three are configured.

In Kubernetes, set `llm.baseUrl` and `llm.model` in Helm values and supply the key as `secrets.llmApiKey`; the chart puts it in the `urumi-secrets` Secret and injects it into the gateway from that Secret. Use a protected file with Helm `--set-file secrets.llmApiKey=...`; do not put the key in committed values, command-line `--set` arguments, logs, or pod arguments. Helm release data retains values. This chart currently creates its Secret from Helm values rather than referencing an externally managed Secret, so production deployments that require external secret management need that integration configured before use.

The WooCommerce MCP exposes `get_products`, `get_orders`, `get_customer`,
`create_order`, and the existing product/order tools. `create_order` is
restricted to an explicitly requested, unpaid pending test order and marks it
with `_urumi_test_order`; it accepts no customer details and never marks an
order paid. A success response requires WooCommerce to confirm the pending,
unpaid state and marker; inspect the store before retrying if confirmation
fails. Gateway members need explicit per-tool grants; administrators keep
access to all discovered tools.

## Team invitations
An admin can create a seven-day, one-time invitation with POST /api/invitations using the admin bearer key and JSON body such as {"email":"member@example.com","role":"MEMBER"}. The response contains a one-time invite_token to place in your invitation link or share securely. The invitee accepts with POST /api/invitations/accept and {"token":"...","name":"..."}. Acceptance creates a user and returns a new API key once. Email delivery is not implemented; the invitee completes acceptance in the dashboard using the link fragment.

## Run gateway without Kubernetes (fast loop)
```bash
cd services/gateway && pip install -r requirements.txt
BOOTSTRAP_ADMIN_KEY="$URUMI_LOCAL_ADMIN_KEY" SEED_SERVERS='[{"name":"weather","url":"http://localhost:8001/mcp"}]' uvicorn app.main:app --port 8000
```

Set `URUMI_LOCAL_ADMIN_KEY` in the local shell to a disposable Gateway key
before running this example; do not place it in source control or use it in
production.

## Key design decisions
- Namespaced server__tool names prevent collisions.
- Per-call upstream sessions and timeouts isolate failures.
- User API keys are HMAC-SHA256 hashed and shown once; upstream credentials are Fernet-encrypted at rest.
- Tool permissions are checked during listing and execution.
- MCP and chat tool calls are routed and audited by the gateway rather than calling upstreams directly.

See [docs/STATUS.md](docs/STATUS.md) for the current verified state, exact
validation results, and deployment blockers. Dashboard sign-in uses a Urumi
Gateway API key, separate from `LLM_API_KEY`. The source-level “Invalid key”
fix is not deployed. Do not run `helm upgrade` from this dirty worktree: the
last redacted plan proposed 23 resource changes, including `urumi-secrets` and
NetworkPolicies. See [docs/assessment-gap-matrix.md](docs/assessment-gap-matrix.md)
for remaining assignment acceptance evidence. Local chart validation does not
establish live-store, MCP-client, or production readiness.
Follow [docs/live-acceptance-tests.md](docs/live-acceptance-tests.md) for the
ordered final demo, including the unpaid WooCommerce test-order guard.
