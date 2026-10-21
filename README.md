# Urumi MCP Gateway — AI FDE Internship Assignment

A Kubernetes-deployed MCP gateway that exposes one gateway endpoint for WooCommerce, Weather, and Currency tools. It includes a FastAPI gateway, WooCommerce MCP server, dashboard/chat UI, API-key authentication, role and tool permissions, audit records, health/failure handling, and a Helm chart for local k3d and production-like k3s deployments.

This README is the evaluator-facing entry point for the completed base assignment. The implementation, Kubernetes deployment and core live demonstrations are in place. See [docs/STATUS.md](docs/STATUS.md) for the evidence record and [docs/assessment-gap-matrix.md](docs/assessment-gap-matrix.md) for the requirement-to-implementation mapping.

## Assignment deliverables

| Requirement | Location / evidence |
|---|---|
| One root Helm chart with base, local and production values | `infrastructure/helm/urumi/` — `values.yaml`, `values-local.yaml`, `values-prod.yaml`, and `templates/` |
| WordPress + WooCommerce backed by MySQL and persistent volumes | Helm WordPress, setup Job, MySQL, and PVC resources |
| Candidate-built WooCommerce MCP | `services/woo-mcp/` — product, order and customer tools plus WooCommerce REST client |
| One MCP gateway aggregating at least three upstreams | `services/gateway/` — WooCommerce, Weather and Currency |
| Dashboard and model-backed tool-calling chat | `dashboard/` and gateway chat API; provider configured through OpenAI-compatible chat-completions settings |
| Authentication, authorization and audit | Gateway API keys, admin/member roles, per-tool permissions, revocation, and audit records |
| Security and operations | Kubernetes Secrets wiring, NetworkPolicy templates, probes/resources, health handling and deployment guard |
| Tests and handoff | `tests/`, `.github/workflows/ci.yml`, and `docs/` |

## Architecture

```text
Dashboard / Chat / MCP Inspector / compatible client
                         |
                         | Gateway API key
                         v
                 Urumi Gateway (/mcp)
             authenticate -> authorize -> route
                 audit + bounded timeouts
                  /        |        \
                 v         v         v
             Woo MCP   Weather MCP  Currency MCP
                 |
           WooCommerce REST API
                 |
       WordPress + WooCommerce
                 |
              MySQL + PVC

PostgreSQL + PVC: users, API-key hashes, server/tool catalog,
permissions, invitations and audit records.
Helm: Deployments, Services, Ingress, storage, Secrets and NetworkPolicies.
```

The gateway is the control point. Clients and chat should not call upstream services directly. Tool names are namespaced by upstream server to avoid collisions. Permissions are checked for both discovery and execution; missing MEMBER tool grants default-deny.

## Repository map

- `services/gateway/` — FastAPI gateway, MCP endpoint/client, auth/RBAC, routing, admin APIs, chat and audit
- `services/woo-mcp/` — WooCommerce MCP server, REST client and product/order tools
- `services/weather-mcp/` and `services/currency-mcp/` — additional MCP upstreams
- `dashboard/` — React + TypeScript + Vite UI
- `infrastructure/helm/urumi/` — single Helm chart and local/production overlays
- `scripts/dev.sh` — local image build/import and Helm deployment workflow
- `tests/` — gateway, Helm, Woo MCP and integration checks
- `docs/STATUS.md` — current evidence and outstanding gates
- `docs/system-design.md` — architecture, trade-offs and production changes
- `docs/threat-model.md` — threats, controls and residual risks
- `docs/mcp-flow.md` — MCP request flow
- `docs/live-acceptance-tests.md` — ordered live acceptance procedure
- `docs/assessment-gap-matrix.md` — requirement-to-evidence matrix

## Local setup (Windows + k3d)

Install Git, Docker Desktop with Linux containers, Python 3.12, Node.js 22, kubectl, Helm and k3d. Then clone and inspect the working tree:

```powershell
git clone https://github.com/MananBhutada/urumi-mcp-gateway.git
Set-Location .\urumi-mcp-gateway
git status --short
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r services\gateway\requirements.txt
python -m pip install -r services\woo-mcp\requirements.txt
python -m pip install pytest
Push-Location dashboard
npm ci
Pop-Location
```

To deploy the disposable local environment, review `scripts/dev.sh` and the current Helm release first, then run it from a Bash-compatible shell with Docker, k3d and Helm available:

```bash
./scripts/dev.sh
```

**This command changes cluster resources.** The script checks the local context/release and has a confirmation gate for an existing release, but you must still review its proposed changes. Do not run it against a shared or production cluster or use it as a shortcut to upgrade the existing revision-7 environment.

On Windows, add the following hosts entry using an elevated editor:

```text
127.0.0.1 store.urumi.local dashboard.urumi.local
```

Open:

- Dashboard: http://dashboard.urumi.local
- Storefront: http://store.urumi.local
- WordPress admin: http://store.urumi.local/wp-admin/

The local Helm overlay currently contains disposable demo values. Do not reuse them outside an isolated demo environment. A separate secrets audit/rotation and Git-history review remains an explicit follow-up; this documentation update does not claim that the repository has been cleared of all credential risks.

## Sign in and use the gateway

### Dashboard

1. Open the dashboard URL.
2. Sign in using a **Urumi Gateway API key** for the intended user.
3. Use the server/tool views and Team controls available to the current build.
4. Use chat after the OpenAI-compatible provider is configured.

A Gateway API key and an LLM-provider key are different credentials. `LLM_API_KEY` authenticates Urumi to the model provider; it is not a dashboard login key. A `401` from `GET /api/me` means the supplied Gateway key was not accepted.

### MCP Inspector or another compatible client

Configure one endpoint:

- URL: `http://dashboard.urumi.local/mcp`
- Header: `Authorization: Bearer <URUMI_GATEWAY_API_KEY>`

Initialize a session, call `tools/list`, then try a read-only tool such as Weather, Currency or WooCommerce product/order lookup. Confirm tool names from the **running deployment**, since local source changes are not proof that the current image has been deployed. Do not paste keys into chat, issue comments, screenshots or source control.

### WooCommerce order flow

1. Open the storefront and choose a disposable test product.
2. Add it to the cart and complete checkout using test-only details and the configured dummy/Cash-on-Delivery payment method.
3. Record the order number/status and verify the order, line items, total and payment method in WordPress Admin.
4. The MCP `create_order` tool is guarded for a specifically requested pending/unpaid test order: it requires the test flag, accepts no customer details and does not mark an order paid. Verify the returned order and marker in the store before retrying a request whose response is uncertain.

Use only a disposable local store. Do not create test orders against a real customer's or production store's data.

## Model-provider configuration

The chat layer expects an OpenAI-compatible chat-completions API. Configure:

- `LLM_BASE_URL` — provider base URL
- `LLM_MODEL` — exact model identifier supported by the provider
- `LLM_API_KEY` — provider credential, supplied through a protected environment/Secret path

For Helm, set `llm.baseUrl` and `llm.model`, and provide the key through the chart's Secret wiring. The current chart creates Kubernetes Secret content from Helm values; Helm release data can retain supplied values. External Secret Manager integration is **not** claimed as complete. Use a protected secret-injection workflow and do not put real credentials in committed values or command history. Live chat behavior should be evaluated from the recorded demo and current deployment, not inferred from configuration alone.

## Production-like VPS / k3s deployment

The chart includes `values-prod.yaml` as a starting profile, not a one-command production guarantee. Before a VPS deployment:

1. Provision a supported Kubernetes/k3s cluster, container registry access, DNS records and a supported storage class.
2. Set real domain names and configure Ingress/TLS with a valid certificate and referenced TLS Secret.
3. Build and publish versioned images, then set their registry paths and pull policy.
4. Supply unique credentials through an approved secret manager or protected deployment-time injection. Do not commit populated production values. The chart's current Secret-from-values approach and Helm release storage behavior must be addressed before claiming external-secret-manager-grade production handling.
5. Review resource requests/limits, replicas, persistence, backup/restore, network policy enforcement, ingress exposure, logs, upgrades and rollback.
6. Run the live acceptance checklist against that target and record evidence. A successful local Helm render does not establish VPS readiness.

See [docs/system-design.md](docs/system-design.md) for production-specific design changes and [docs/live-acceptance-tests.md](docs/live-acceptance-tests.md) for safe validation steps.

## Tests and validation

The repository has automated gateway, Helm and Woo MCP tests, plus a dashboard production build and CI workflow. The current evidence record lists the exact recorded commands and results in [docs/STATUS.md](docs/STATUS.md). Results are tied to the environment and revision in which they ran; this README update did not rerun tests.

Useful checks from the repository root include:

```powershell
python -m pytest -q tests/gateway
python -m pytest -q tests/helm
python -m pytest -q tests/woo_mcp
npm run build --prefix dashboard
helm lint infrastructure/helm/urumi -f infrastructure/helm/urumi/values-local.yaml
helm template urumi infrastructure/helm/urumi -f infrastructure/helm/urumi/values-local.yaml
helm lint infrastructure/helm/urumi -f infrastructure/helm/urumi/values-prod.yaml
helm template urumi infrastructure/helm/urumi -f infrastructure/helm/urumi/values-prod.yaml
```

Run commands in the supported environment with the needed dependencies installed. The test suite may have environment-specific prerequisites; report actual results rather than assuming a command passed.

## Additional engineering work

The project includes additional work beyond the base service wiring:

- **Member tool-level access control:** MEMBER tools default-deny without an explicit grant; the Team UI exposes grant/deny controls. Key revocation and rejection of the old key have been demonstrated.
- **Upstream failure isolation and operator controls:** Weather can be disabled so its tools disappear; an outage is shown as unreachable while Currency remains usable, and restoring Weather restores service availability.
- **Network segmentation:** default-deny/scoped NetworkPolicy rules, narrow MySQL ingress and database egress denial are present in the chart and Helm-rendered checks.
- **Security controls:** hashed Gateway keys, encrypted stored upstream credentials, audit attribution and upstream URL validation are implemented in code/tests.
- **Shared catalog:** the tool catalog is database-backed for cross-replica consistency.
- **Team invitations:** one-time, expiring invitation API and basic dashboard UI are implemented. Email delivery is intentionally not included.
- **Production profile:** production values and a deployment runbook are provided for adapting the working chart to a target environment.

The base assignment is complete in the demonstrated local Kubernetes scope. Production deployment-specific activities—such as provisioning a public VPS, wiring real DNS/TLS, external secret-manager integration and a backup/restore drill—are deployment operations, not missing base application features.

## Demo evidence

The developer has recorded local live-demo videos showing:

- WooCommerce storefront checkout/order confirmation and verification in WordPress Admin.
- Admin-side chat retrieving WooCommerce order information.
- Chat using Weather and Currency tools.
- MCP Inspector order-tool invocation.
- Member key revocation and rejection of the revoked key.
- Dashboard server/status visibility and Weather enable/disable behavior.
- Weather upstream outage isolation while Currency continues to work, followed by recovery.
- Kubernetes workload health.

The videos are held separately by the candidate; no public video URL is included in this repository. The submission form should contain the appropriate video link(s). The recording set demonstrates the listed flows, but does not by itself prove persistence after pod restart, NetworkPolicy enforcement at the packet level, a production VPS deployment, or a fresh-cluster installation.

## Scope notes

The assignment deliverable is demonstrated in the local Kubernetes environment. The following are environment-specific deployment considerations rather than blockers to the completed local assignment:

- The MCP endpoint uses stateless JSON responses; compatibility should be judged against the target client's supported Streamable HTTP behavior.
- The chart currently renders Kubernetes Secret content from Helm values, which may be retained in Helm release data. A separate credential audit/rotation and Git-history review is tracked independently; never commit real credentials.
- NetworkPolicy objects are rendered in the chart; enforcement in a target cluster depends on its CNI and should be validated during deployment.
- Invitation creation/acceptance is implemented; the flow does not send email.
- The production profile is a starting point for a target VPS/k3s environment and requires environment-specific DNS, TLS, storage, secrets and operational configuration.
- Database schema evolution does not yet use an Alembic migration workflow.

For the most accurate source-versus-live state, start with [docs/STATUS.md](docs/STATUS.md), then follow [docs/assessment-gap-matrix.md](docs/assessment-gap-matrix.md) and [docs/live-acceptance-tests.md](docs/live-acceptance-tests.md).
