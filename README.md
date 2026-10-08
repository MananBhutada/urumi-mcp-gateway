# Urumi MCP Gateway

A small but real **MCP control plane**: one gateway endpoint federating many MCP servers, with API-key auth, RBAC,
per-role tool permissions, audit logging, failure isolation, a dashboard and a chat agent — deployed with one Helm chart
on k3d locally and k3s in production.

```
Dashboard / Chat / Cursor / MCP Inspector → ONE GATEWAY URL (/mcp) → woocommerce | weather | currency MCP servers
                                                   │                          └→ WooCommerce REST → WordPress → MySQL(PVC)
                                                   └→ PostgreSQL (users, keys, servers, audit)
```

## Layout
- `services/gateway` FastAPI gateway: MCP server (Streamable HTTP, `POST /mcp`) + MCP client (official SDK) + admin API + chat
- `services/woo-mcp` WooCommerce MCP (5 tools) · `weather-mcp` · `currency-mcp`
- `dashboard` React + TS + Vite
- `infrastructure/helm/urumi` single chart; `values-local.yaml` / `values-prod.yaml`
- `docs/` architecture, threat model, MCP flow, demo script, status

## Quick start (local)
```bash
./scripts/dev.sh                       # k3d cluster, build+import images, helm install
echo "127.0.0.1 store.urumi.local dashboard.urumi.local" | sudo tee -a /etc/hosts
# storefront:  http://store.urumi.local      dashboard: http://dashboard.urumi.local
# admin API key: secrets.bootstrapAdminKey in values.yaml (change it!)
```
MCP client config (Cursor / Inspector): URL `http://dashboard.urumi.local/mcp`, header `Authorization: Bearer <member key>`.

## Run gateway without Kubernetes (fast loop)
```bash
cd services/gateway && pip install -r requirements.txt
BOOTSTRAP_ADMIN_KEY=urumi_live_dev SEED_SERVERS='[{"name":"weather","url":"http://localhost:8001/mcp"}]' uvicorn app.main:app --port 8000
cd ../weather-mcp && PORT=8001 python -m app.main
KEY=urumi_live_dev tests/integration/smoke.sh
```

## Key design decisions
- **Namespacing** `server__tool` removes collisions. **Failure isolation**: per-call sessions with connect/call timeouts; a dead upstream becomes `unreachable` and its tools vanish, others keep working.
- **Credentials**: user API keys stored as HMAC-SHA256 hashes (raw shown once); upstream credentials Fernet-encrypted, write-only in the API.
- **Permissions**: role-based tool deny → hidden from `tools/list` AND rejected on direct `tools/call`.
- **Audit** is inside the routing path (MCP and chat both), not a UI feature.
- **Chat** goes LLM → gateway router → upstream, never directly to an MCP server.

See `docs/STATUS.md` for what is verified vs. still to do.
