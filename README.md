# Urumi MCP Gateway

An original MCP gateway/control plane: one MCP endpoint federating multiple MCP servers, with per-user API keys, role and tool permissions, audit logging, failure isolation, an admin dashboard, and a tool-calling chat agent. The deployment target is one Helm chart for local k3d and production-like k3s.

```
Dashboard / Chat / Cursor / MCP Inspector → ONE GATEWAY URL (/mcp) → woocommerce | weather | currency MCP servers
                                                   │                          └→ WooCommerce REST → WordPress → MySQL(PVC)
                                                   └→ PostgreSQL (users, keys, invitations, servers, audit)
```

## Layout
- services/gateway: FastAPI gateway, MCP server/client, admin API, chat and audit
- services/woo-mcp: candidate-written WooCommerce MCP (5 product/order tools)
- services/weather-mcp and services/currency-mcp: additional upstream MCPs
- dashboard: React + TypeScript + Vite
- infrastructure/helm/urumi: one chart with local and production values
- docs: architecture, threat model, MCP flow, demo script, status and assessment gap matrix

## Quick start (local)
```bash
./scripts/dev.sh
echo "127.0.0.1 store.urumi.local dashboard.urumi.local" | sudo tee -a /etc/hosts
```
The local-only bootstrap admin key is set in infrastructure/helm/urumi/values-local.yaml under secrets.bootstrapAdminKey. It is a disposable demo credential and must never be reused in production.

MCP client config (Cursor / Inspector): URL http://dashboard.urumi.local/mcp, header Authorization: Bearer <member key>.

## Production values
Use values-prod.yaml and provide unique secrets through a secret manager or deployment-time secret injection. The production gateway refuses to start with a weak gateway secret, a weak bootstrap admin key, or SQLite. Do not commit real credentials or a populated production values file.

## Team invitations
An admin can create a seven-day, one-time invitation with POST /api/invitations using the admin bearer key and JSON body such as {"email":"member@example.com","role":"MEMBER"}. The response contains a one-time invite_token to place in your invitation link or share securely. The invitee accepts with POST /api/invitations/accept and {"token":"...","name":"..."}. Acceptance creates a user and returns a new API key once. Email delivery and a polished invite-acceptance screen are not yet implemented; the API is ready for that UI integration.

## Run gateway without Kubernetes (fast loop)
```bash
cd services/gateway && pip install -r requirements.txt
BOOTSTRAP_ADMIN_KEY=urumi_live_dev SEED_SERVERS='[{"name":"weather","url":"http://localhost:8001/mcp"}]' uvicorn app.main:app --port 8000
```

## Key design decisions
- Namespaced server__tool names prevent collisions.
- Per-call upstream sessions and timeouts isolate failures.
- User API keys are HMAC-SHA256 hashed and shown once; upstream credentials are Fernet-encrypted at rest.
- Tool permissions are checked during listing and execution.
- MCP and chat tool calls are routed and audited by the gateway rather than calling upstreams directly.

See docs/STATUS.md and docs/assessment-gap-matrix.md for the distinction between implemented code and requirements still awaiting live proof.
