# Urumi MCP Gateway — Assignment Handoff

## Local README version

# Urumi MCP Gateway

An original MCP gateway/control plane: one MCP endpoint federating multiple MCP servers, with per-user API keys, role and tool permissions, audit logging, failure isolation, an admin dashboard, and a tool-calling chat agent. The deployment target is one Helm chart for local k3d and production-like k3s.

```
Dashboard / Chat / Cursor / MCP Inspector ΓåÆ ONE GATEWAY URL (/mcp) ΓåÆ woocommerce | weather | currency MCP servers
                                                   Γöé                          ΓööΓåÆ WooCommerce REST ΓåÆ WordPress ΓåÆ MySQL(PVC)
                                                   ΓööΓåÆ PostgreSQL (users, keys, invitations, servers, audit)
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
Gateway API key, separate from `LLM_API_KEY`. The source-level ΓÇ£Invalid keyΓÇ¥
fix is not deployed. Do not run `helm upgrade` from this dirty worktree: the
last redacted plan proposed 23 resource changes, including `urumi-secrets` and
NetworkPolicies. See [docs/assessment-gap-matrix.md](docs/assessment-gap-matrix.md)
for remaining assignment acceptance evidence. Local chart validation does not
establish live-store, MCP-client, or production readiness.
Follow [docs/live-acceptance-tests.md](docs/live-acceptance-tests.md) for the
ordered final demo, including the unpaid WooCommerce test-order guard.

---

## GitHub README version

# Urumi AI FDE Internship ΓÇö Completed Assignment: MCP Gateway on Kubernetes

**Assignment status: implementation deliverables are assembled in this repository.** This is the completed-project handoff for the Urumi AI FDE Internship Round 1 assignment: Kubernetes/Helm deployment, WordPress + WooCommerce, WooCommerce MCP integration, the multi-upstream MCP Gateway, dashboard, authentication/authorization, audit trail, optional model-backed tool-calling chat, automated tests, CI configuration, and operational documentation.

The README explains how to clone, configure, deploy, use, and validate the project. Automated/local checks and live-cluster acceptance are reported separately so a reviewer can distinguish code and test evidence from actions that require a running environment. See [docs/STATUS.md](docs/STATUS.md) for the dated verification record and [docs/assessment-gap-matrix.md](docs/assessment-gap-matrix.md) for the requirement-to-evidence mapping.

## 1. Assignment scope and deliverables

The project addresses the core FDE assignment areas:

- **Kubernetes/Helm:** one chart at `infrastructure/helm/urumi`, shared defaults, local and production value overlays, Deployments, Services, Ingress, PVCs, probes/resources, Secrets wiring, and NetworkPolicy templates.
- **Store:** WordPress + WooCommerce backed by MySQL and persistent storage.
- **Gateway:** FastAPI service exposing one Streamable HTTP MCP endpoint (`/mcp`) and routing namespaced tool calls to upstream MCP servers.
- **MCP integrations:** WooCommerce, Weather, and Currency upstream services.
- **Dashboard:** React, TypeScript, and Vite UI for gateway operations and chat.
- **Identity and controls:** gateway API keys, admin/member roles, tool-level authorization, invitations, and audit records.
- **Model integration:** optional OpenAI-compatible chat-completions provider with tool calling; the provider key is separate from gateway user keys.
- **Quality and handoff:** automated tests, CI workflow, architecture/flow/runbook/acceptance documentation, and reproducible local commands.

The assignment implementation is organized around these deliverables:

| FDE deliverable | Repository implementation |
|---|---|
| Root Helm chart with base, local and production values | `infrastructure/helm/urumi/Chart.yaml`, `values.yaml`, `values-local.yaml`, `values-prod.yaml` and `templates/` |
| Kubernetes workloads and service discovery | Gateway, dashboard, Woo MCP, Weather MCP, Currency MCP, WordPress, MySQL and PostgreSQL resources with Services and probes |
| Persistent store | MySQL data PVC, WordPress content PVC and PostgreSQL data PVC |
| WordPress + WooCommerce | Automated setup Job and storefront configuration |
| WooCommerce MCP tools | Product/order tool implementation and WooCommerce REST client in `services/woo-mcp/` |
| One aggregated MCP endpoint | Gateway MCP server and upstream routing under `services/gateway/app/mcp/` and `services/gateway/app/routing/` |
| Gateway dashboard | React + TypeScript app under `dashboard/` |
| Authentication and access control | Gateway user keys, admin/member roles, per-tool permissions and invitation API |
| Audit trail | Gateway audit recording and admin-facing API |
| Optional LLM tool-calling chat | OpenAI-compatible provider configuration and gateway-routed tool calls |
| Secrets and network isolation | Kubernetes Secret references and NetworkPolicy templates in the Helm chart |
| Automated quality checks | Gateway/Helm/Woo MCP tests, dashboard build and `.github/workflows/ci.yml` |
| Handoff and assessment documentation | Architecture, MCP flow, deployment runbook, live acceptance procedure, status record and gap matrix |

The assignment's essential infrastructure and application code is represented in this repository. Live end-to-end acceptance must be assessed from actual run evidence, not inferred from source code or successful Helm rendering.

## 2. Architecture and request flow

```text
Browser / Dashboard Chat / Cursor / MCP Inspector
                    |
                    | one Gateway URL + Urumi user API key
                    v
        Dashboard proxy / Gateway API
                    |
          authenticate + authorize
          resolve namespaced tool
          enforce timeout + audit
                    |
        +-----------+------------+
        |           |            |
        v           v            v
  WooCommerce    Weather      Currency
      MCP          MCP          MCP
        |
  WooCommerce REST API
        |
 WordPress + WooCommerce
        |
      MySQL + PVC

PostgreSQL + PVC: gateway users, key hashes, server registry,
invitations, permissions and audit data.
Kubernetes Secrets: runtime credentials.
Helm: Deployments, Services, Ingress, storage and NetworkPolicies.
```

**Typical MCP call:** client ΓåÆ `/mcp` ΓåÆ authenticate the caller ΓåÆ filter/authorize the requested namespaced tool ΓåÆ call the matching upstream MCP server ΓåÆ record the outcome ΓåÆ return the result.

The gateway is the control point: clients and the chat agent should not call upstream services directly. WooCommerce operations go through its REST API; the gateway does not query the commerce database directly.

## 3. Repository map

| Path | Purpose |
|---|---|
| `services/gateway/` | FastAPI gateway, MCP server/client, authentication, API/admin routes, routing, chat and audit |
| `services/woo-mcp/` | WooCommerce MCP server, REST client and product/order tools |
| `services/weather-mcp/` | Weather MCP integration |
| `services/currency-mcp/` | Currency MCP integration |
| `dashboard/` | React + TypeScript UI, Vite build, same-origin API/proxy configuration |
| `infrastructure/helm/urumi/` | Helm chart and local/production configuration |
| `scripts/dev.sh` | Build/import local images and install/upgrade the local Helm release |
| `scripts/test.sh` | Test helper script |
| `scripts/seed.sh` | Development seed helper |
| `tests/` | Gateway, Helm, Woo MCP and integration tests |
| `.github/workflows/ci.yml` | CI workflow |
| `docs/architecture.md` | System architecture and trust boundaries |
| `docs/mcp-flow.md` | MCP request lifecycle |
| `docs/store-deployment-runbook.md` | Store and deployment runbook |
| `docs/live-acceptance-tests.md` | Manual/live acceptance procedure |
| `docs/implementation-checklist.md` | Assignment acceptance checklist |
| `docs/assessment-gap-matrix.md` | Requirement-to-evidence and gap matrix |
| `docs/STATUS.md` | Dated, evidence-based state and verification history |

## 4. Requirements

For a full local Kubernetes run, install:

- Git
- Docker Desktop (Linux containers enabled)
- Python 3.12
- Node.js 22 and npm
- kubectl
- Helm 3-compatible CLI
- k3d

PowerShell examples below are intended for Windows. Run cluster-changing commands only when you intend to create/update the local cluster and release.

## 5. Clone and prepare on a new computer

Clone the repository and inspect the branch and working tree before editing:

```powershell
git clone https://github.com/MananBhutada/urumi-mcp-gateway.git
Set-Location .\urumi-mcp-gateway
git switch main
git pull --ff-only origin main
git status --short
```

Create a Python environment and install the application/test dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r services\gateway\requirements.txt
python -m pip install -r services\woo-mcp\requirements.txt
python -m pip install pytest
Push-Location dashboard
npm ci
Pop-Location
```

If PowerShell blocks virtual-environment activation, use an approved execution-policy setting for the current user or invoke the environment's Python directly. Do not delete or reset local changes just to make a pull succeed; inspect and preserve them first.

## 6. Run the local Kubernetes deployment

> **Warning:** `scripts/dev.sh` creates the `urumi` k3d cluster if needed, builds and imports images, and runs `helm upgrade --install`. It changes cluster resources. Review the chart and current release before running it; do not use it against a shared/production cluster.

From a Bash-compatible shell with Docker, k3d and Helm configured:

```bash
export ANTHROPIC_API_KEY=""   # optional legacy script variable; leave empty unless deliberately configured
./scripts/dev.sh
```

The script builds the Gateway, Woo MCP, Weather MCP, Currency MCP and dashboard images, imports them into k3d, then installs/upgrades the `urumi` release with `values-local.yaml`.

For Windows, add this line to the hosts file as Administrator:

```text
127.0.0.1 store.urumi.local dashboard.urumi.local
```

Hosts file: `C:\Windows\System32\drivers\etc\hosts`.

After the cluster and Ingress are ready, open:

- **Dashboard:** http://dashboard.urumi.local
- **Storefront:** http://store.urumi.local

If a host does not resolve, check the hosts file and the k3d load-balancer/Ingress before changing application configuration.

### Local credentials and secrets

The local values file contains **disposable demo-only credentials** so the local assignment can be brought up easily. The configured bootstrap key is in `infrastructure/helm/urumi/values-local.yaml` under `secrets.bootstrapAdminKey`. Use only that local demo key for the local installation, and replace it with a fresh key if the environment is shared. Never reuse it in production or commit real credentials.

A bootstrap key is not a general-purpose reset mechanism. Once the admin user exists, changing the configured bootstrap value may not replace the already-created user's active API key. Preserve the database and use the documented authentication/recovery process rather than repeatedly changing values or redeploying blindly.

## 7. How to use the application

### Dashboard sign-in

1. Open http://dashboard.urumi.local.
2. Sign in with a **Urumi Gateway API key** belonging to the configured admin/user.
3. Use the dashboard to inspect/manage the gateway features available to that role, including MCP server/tool state, users/keys/permissions/invitations and audit information as exposed by the current build.
4. Use chat only after a compatible model provider has been configured.

**Do not paste an OpenRouter/LLM provider key into the dashboard login field.** The provider key authenticates the gateway to the model provider; a Urumi Gateway API key authenticates a user to Urumi. A `401` from `GET /api/me` means the gateway did not accept the supplied user key; it does not prove that the LLM provider key is invalid.

The latest source/live distinction and the known dashboard-image deployment issue are recorded in [docs/STATUS.md](docs/STATUS.md).

### Connect Cursor or MCP Inspector

Configure the client with the gateway MCP endpoint:

- **URL:** `http://dashboard.urumi.local/mcp`
- **Header:** `Authorization: Bearer <URUMI_GATEWAY_API_KEY>`

Use a user key with only the permissions needed for the demonstration. The gateway prefixes discovered tools with the upstream server name (for example, `woocommerce__list_products`) to avoid name collisions. Check the current `tools/list` response from the running deployment rather than assuming that a local source change is already deployed.

Recommended protocol walkthrough:

1. Initialize an MCP session.
2. Call `tools/list` and record the names returned by the **running** gateway.
3. Call a read-only Weather, Currency or WooCommerce tool.
4. Verify the result came back through the single gateway endpoint.
5. Verify the call is audited.
6. If demonstrating authorization, use a dedicated test member/key and verify denied tools are not listed and cannot be called directly.
7. Only test key revocation, upstream disabling or outage isolation in a disposable environment.

### WooCommerce storefront

1. Open http://store.urumi.local.
2. Confirm the published test product is visible.
3. Add it to the cart and proceed to checkout.
4. Use test-only customer details and the configured test payment method.
5. Place a test order and record its order number/status.
6. Verify the order and line items in WordPress/WooCommerce Admin.

Do not use real customer information or create a live order unintentionally. Product/order creation and checkout are state-changing operations. The manual acceptance steps, including persistence checks, are in [docs/live-acceptance-tests.md](docs/live-acceptance-tests.md).

## 8. Configure the optional chat model

The chat layer uses an OpenAI-compatible chat-completions API. It requires all of:

- `LLM_BASE_URL`: provider API base URL (for example, `https://openrouter.ai/api/v1`)
- `LLM_MODEL`: exact model identifier supported by the provider
- `LLM_API_KEY`: provider credential

The selected model/provider must support tool/function calling for agentic tool use. An empty or invalid provider configuration means chat may remain unavailable even while the Gateway MCP endpoint works.

For Helm, configure `llm.baseUrl` and `llm.model`, and inject the provider key through `secrets.llmApiKey` using a protected file or approved secret-delivery mechanism. The chart currently creates `urumi-secrets` from Helm values; Helm release data can retain supplied values. Do not commit provider keys, paste them into source files, print Kubernetes Secret values, or put secrets in command history. Production use requiring an external secret manager needs that integration configured and reviewed.

## 9. Team invitations and access control

The gateway supports admin/member concepts, API keys and invitation routes. The API-level invitation flow is:

1. An authenticated admin creates a time-limited invitation with `POST /api/invitations`, supplying the intended email and role.
2. The response returns a one-time invitation token. Share it securely; do not commit it or log it.
3. The invitee accepts through `POST /api/invitations/accept` with the token and name.
4. The new user's API key is returned once. Store it securely; the server stores a hash rather than the raw key.

Email delivery is not implemented by this API flow; the token must be delivered by a separate secure channel. Validate role boundaries, explicit member tool permissions, revocation, and audit attribution using the live-acceptance procedure before relying on them operationally.

## 10. Run tests and validate the chart

Run from the repository root. These checks are local validation; they do not deploy anything.

### Python tests

```powershell
py -3.12 -m pytest -q tests/gateway tests/helm
Push-Location services\woo-mcp
py -3.12 -m pytest -q ..\..\tests\woo_mcp
Pop-Location
```

### Dashboard production build

```powershell
Push-Location dashboard
npm ci
npm run build
Pop-Location
```

### Helm lint and render

```powershell
helm lint infrastructure/helm/urumi -f infrastructure/helm/urumi/values.yaml -f infrastructure/helm/urumi/values-local.yaml
helm lint infrastructure/helm/urumi -f infrastructure/helm/urumi/values.yaml -f infrastructure/helm/urumi/values-prod.yaml
helm template urumi infrastructure/helm/urumi -f infrastructure/helm/urumi/values.yaml -f infrastructure/helm/urumi/values-local.yaml
helm template urumi infrastructure/helm/urumi -f infrastructure/helm/urumi/values.yaml -f infrastructure/helm/urumi/values-prod.yaml
```

### Additional source checks

```powershell
py -3.12 -m compileall -q services\gateway\app
git diff --check
```

The verification record in [docs/STATUS.md](docs/STATUS.md) documents previously observed passing test/build/lint/render results and their scope. Re-run the commands on the exact commit being submitted and inspect the CI result; do not treat historical results as proof that a later commit or a fresh cluster passed.

## 11. Production-like deployment notes

Use `infrastructure/helm/urumi/values-prod.yaml` only after replacing every example hostname, image reference and placeholder with environment-specific values. Before a production deployment:

- use TLS and valid DNS names;
- use unique, high-entropy secrets delivered securely;
- configure persistent volumes and a tested backup/restore plan;
- confirm image tags exist in a registry reachable by the cluster;
- review resource requests/limits, probes, Ingress exposure and NetworkPolicy selectors;
- verify the CNI actually enforces NetworkPolicies;
- ensure only intended public endpoints are exposed;
- use least-privilege WooCommerce REST credentials;
- validate the Helm diff/plan and preserve existing Secrets and PVCs;
- test a rollback and recovery procedure.

The current chart creates a Kubernetes Secret from Helm values rather than automatically integrating with an external secret manager. Treat that as a production integration requirement where policy demands externally managed secrets. A successful `helm lint` or `helm template` is not proof of production readiness.

**Do not run a production upgrade from an unreviewed working tree.** The status record describes a prior dry-run that proposed unrelated resource changes, including Secret and NetworkPolicy changes. Reconcile the installed release values and review a redacted plan before any approved upgrade. Never expose Secret data while troubleshooting.

## 12. Troubleshooting

| Symptom | Check |
|---|---|
| `dashboard.urumi.local` or `store.urumi.local` does not open | Hosts file, k3d load balancer, Ingress controller and Ingress host values |
| Dashboard says ΓÇ£Invalid keyΓÇ¥ | Use a Urumi Gateway user key, not the LLM/OpenRouter provider key; verify the running dashboard image matches the intended source |
| Dashboard loads but chat fails | Provider base URL, exact model ID, provider key Secret reference, provider availability and tool-calling support |
| A tool is missing | Query `tools/list` on the deployed gateway; check upstream health/enablement, role and tool permissions, and whether the intended image is deployed |
| WooCommerce REST requests fail on local HTTP | Confirm the local-only configuration and OAuth signing behavior; do not disable authentication or expose Woo credentials |
| Helm upgrade proposes unexpected changes | Stop. Review the redacted diff, values and existing Secret/PVC ownership before applying anything |
| A clean clone differs from another computer | Check `git status --short`, `git log -5 --oneline`, and `git ls-remote origin refs/heads/main`; compare the actual commit SHAs instead of assuming a push succeeded |

## 13. Assignment completion and verification evidence

The assignment's implementation deliverables are present in the repository, with the architecture, deployment profiles, automated tests, CI workflow and operator handoff documented. The dated verification record reports the following results for the working tree it reviewed: Gateway/Helm tests passed, Woo MCP tests passed, dashboard production build passed, local and production Helm lint/render passed, rendered YAML parsed, and client-side Kubernetes manifest validation passed. These are recorded results for that reviewed working tree, not an assertion that every later GitHub commit or every live acceptance scenario has been rerun.

The following are runtime/demo acceptance checks rather than missing README or repository deliverables; they require evidence from the running environment:

- fresh-clone installation and clean-cluster deployment on the exact submission commit;
- a browser checkout and verification of the resulting WooCommerce order;
- product/order persistence across pod restart and backup/restore;
- external MCP client initialize/list/call against the currently deployed image;
- live admin/member permission, revocation and audit-boundary checks;
- real model-provider tool calling;
- NetworkPolicy enforcement and upstream outage isolation;
- CI result for the exact commit and a recorded demo walkthrough.

Follow [docs/live-acceptance-tests.md](docs/live-acceptance-tests.md), [docs/implementation-checklist.md](docs/implementation-checklist.md), and [docs/assessment-gap-matrix.md](docs/assessment-gap-matrix.md) for the exact checks. The dated [docs/STATUS.md](docs/STATUS.md) is the source of truth for what was actually verified and what remains.

## 14. Security rules

- Never commit real API keys, provider keys, passwords, populated production values, kubeconfig files or Secret exports.
- Do not use the local demo credentials outside a disposable local environment.
- Treat gateway API keys and LLM provider credentials as separate credentials.
- Never print raw Kubernetes Secret data, OAuth query strings, invitation tokens or customer PII.
- Prefer read-only acceptance checks; use disposable data for state-changing operations.
- Do not delete PVCs, reset Git, clean untracked files, or run an unreviewed Helm upgrade to ΓÇ£fixΓÇ¥ a discrepancy.
- After a credential may have been exposed, rotate it through the provider's secure interface and update the runtime Secret only under a reviewed change plan.

## 15. Useful links

- [Repository](https://github.com/MananBhutada/urumi-mcp-gateway)
- [Architecture](docs/architecture.md)
- [MCP flow](docs/mcp-flow.md)
- [Current status and verification record](docs/STATUS.md)
- [Implementation checklist](docs/implementation-checklist.md)
- [Live acceptance tests](docs/live-acceptance-tests.md)
- [Assessment gap matrix](docs/assessment-gap-matrix.md)
- [Store deployment runbook](docs/store-deployment-runbook.md)
