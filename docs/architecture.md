# Urumi MCP Gateway — architecture

## System boundary

The Kubernetes cluster is the trust boundary. Only the dashboard and WooCommerce storefront are exposed through Ingress. The gateway is reached through the dashboard's same-origin proxy for browser use and through its configured MCP endpoint for external MCP clients. WooCommerce MCP, Weather MCP, Currency MCP, MySQL and PostgreSQL are cluster-internal services and must not have public Ingress resources.

## Text architecture diagram

```text
USERS / CLIENTS
  Team members ────────────────┐
  Dashboard chat agent ────────┤
  Claude / Cursor / MCP client ├── Gateway URL + per-user API key
                               │
EXTERNAL ACCESS                │
  dashboard.urumi.local ──┐    │
  store.urumi.local ──────┼─ Ingress Controller
                          │    │
KUBERNETES CLUSTER        │    ▼
  ┌───────────────────────┴─────────────────────────────────────┐
  │ Dashboard (React)                                           │
  │  Admin UI · user/API-key management · chat · audit logs     │
  │        │ same-origin /api and /mcp proxy                     │
  │        ▼                                                     │
  │ Gateway Backend (FastAPI)                                    │
  │  Authentication · RBAC · tool permissions                    │
  │  Registry · aggregation · namespacing · routing               │
  │  Timeout/failure isolation · audit logging                    │
  │  MCP SERVER endpoint (/mcp)                                   │
  │        │                                                     │
  │        └── Gateway MCP CLIENT ── internal MCP HTTP ──┐        │
  │                                                      ▼        │
  │  ┌──────────────────┐ ┌────────────────┐ ┌────────────────┐ │
  │  │ WooCommerce MCP   │ │ Weather MCP    │ │ Currency MCP   │ │
  │  │ products/orders   │ │ forecast       │ │ conversion     │ │
  │  └────────┬─────────┘ └────────────────┘ └────────────────┘ │
  │           │ WooCommerce REST API (credentials from Secret)   │
  │           ▼                                                  │
  │  WordPress + WooCommerce ───────────────► MySQL               │
  │       │                                                     │
  │       └── persistent WordPress content/uploads               │
  │                                                              │
  │  PostgreSQL: gateway users, hashed API keys, registry,        │
  │              invitations, permissions and audit records      │
  │  Kubernetes Secrets: DB passwords, gateway secret,           │
  │                      WP admin credential, Woo REST keys,     │
  │                      upstream MCP credentials                │
  │  PVCs: WordPress files, MySQL data, PostgreSQL data           │
  │  Helm: Deployments/StatefulSets, Services, Ingress,           │
  │        NetworkPolicies, probes, resource requests/limits      │
  └──────────────────────────────────────────────────────────────┘

MCP TOOL CALL:
  Client -> Gateway (/mcp) -> authenticate API key -> authorize tool
         -> resolve namespaced tool -> call upstream MCP -> audit result
         -> return result to the same client.

STOREFRONT ORDER:
  Browser -> store Ingress -> WordPress/WooCommerce -> MySQL.
  WooCommerce MCP reads/manages orders through the WooCommerce REST API;
  the gateway does not connect directly to the store database.
```

## Trust and data flow

1. **Browser and external clients:** dashboard users authenticate to the platform. External MCP clients use one gateway URL and a user-specific API key. Raw keys are shown only at creation; stored key material is hashed.
2. **Gateway:** validates the caller, checks the user's role and explicit tool permissions, resolves the tool through the registry, invokes the upstream MCP server, and writes an audit record with caller, server, tool, duration and outcome.
3. **Upstream servers:** accept calls only from the gateway's internal network path. Their credentials are not returned to clients or sent to the model.
4. **WooCommerce:** the Woo MCP calls the WooCommerce REST API. WooCommerce persists products, orders and customer/store data in MySQL. The gateway must never query MySQL directly for commerce operations.
5. **Secrets and storage:** Kubernetes Secrets provide runtime credentials; PVCs retain WordPress files and database files across pod restarts. A PVC is persistence, not a backup strategy.
6. **Ingress:** only dashboard and storefront hosts are routed publicly. MCP upstreams and database services have no public Ingress. NetworkPolicies should constrain internal traffic to required paths.
7. **Environments:** one Helm chart is rendered with `values-local.yaml` for Kind/k3d and `values-prod.yaml` for a VPS/k3s cluster. Production requires TLS, unique secrets and persistent volumes.

## Required invariants

- The dashboard chat agent and external MCP clients call tools only through the gateway.
- Every tool call is authorized and audited, including failures.
- Disabling an upstream removes its tools from discovery and prevents calls through stale tool lists.
- An unhealthy upstream must not prevent calls to healthy upstreams.
- MySQL and PostgreSQL are distinct data stores with separate credentials and PVCs.
- WooCommerce API credentials, database passwords, gateway signing/encryption keys and user API keys must never be committed as live secrets.
- The architecture diagram describes the target design; only passing tests and live deployment evidence count as proof that a path works.
