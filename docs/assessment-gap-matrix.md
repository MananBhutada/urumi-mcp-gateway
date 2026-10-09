# Assessment gap matrix

This is the working acceptance contract for the take-home. A file existing is not proof that a requirement works; every gate below needs repeatable evidence before the demo.

| Assessment requirement | Implementation location | Current confidence | Acceptance proof still required |
|---|---|---|---|
| WooCommerce storefront, persistent MySQL, cart/checkout, COD or dummy payment, order in admin | Helm WordPress/MySQL templates and WooCommerce setup job | Unverified in Kubernetes | Fresh k3d install; place COD order; verify in wp-admin; restart pods and verify persistence |
| Candidate-written Woo MCP with 5 required product/order tools | services/woo-mcp/app | Code exists; mock integration previously recorded | Test against real WooCommerce; validate input boundaries and error behavior |
| MCP Streamable HTTP gateway at one URL | services/gateway/app/mcp/server.py | Local SDK path previously recorded passing; compatibility incomplete | Run MCP Inspector or Cursor against /mcp; test initialize, tools/list, tools/call, notifications, malformed JSON-RPC and auth failures |
| Aggregate at least 3 upstreams | services/gateway/app/routing and weather/currency/Woo MCPs | 9 tools reported in local test | Re-run scripted cross-upstream calls; prove namespace collision handling |
| Add/edit/disable/remove upstream registry | services/gateway/app/api/admin.py and dashboard | Backend operations exist; dashboard edit UX incomplete | Browser-test every control; disabled tools disappear promptly and stale cache cannot call disabled server |
| Per-user keys, revocation, roles | services/gateway/app/auth and admin API | Local tests previously recorded | External client key works; revoke then next call returns 401; non-admin receives 403 on all admin routes |
| Audit each tool call with user, server, tool, time, duration and outcome | services/gateway/app/audit and routing | Code exists; failure semantics need testing | Success and error each produce exactly one attributed row; verify chat and external MCP source |
| Chat calls tools only through gateway | services/gateway/app/api/chat.py | Code exists; live model integration untested | Prove chat cannot call upstream directly; prompt requires tools from Woo plus Weather or Currency |
| Team invitations | Admin API/dashboard | Missing in last review | Implement token expiry, one-time acceptance and role assignment, or explicitly track as outstanding |
| Failure isolation | Health refresh and routing | Local Weather-MCP stop test previously recorded | Kill one pod in Kubernetes; its tools become unavailable while the other two continue answering |
| Helm local and production values | infrastructure/helm/urumi | Chart exists; rendering unverified | helm lint and helm template for both values files; deploy same chart on k3d and k3s |
| Secrets and runtime hardening | chart secrets, gateway config and NetworkPolicies | Partially hardened in this branch | Confirm no live credentials are committed, weak production config fails startup, and upstream/DB have no public ingress |
| External MCP client demo and video | docs/demo-script.md | Not yet proven | Record one endpoint/key, multi-upstream call, key revocation, server disable and one-upstream outage |

## Reference-project lessons adopted (not copied wholesale)

- Fiberplane: operations UI should expose server editing/health, tool inventory and inspectable audit/traffic evidence.
- uni-mcp-gateway: single endpoint, per-key access boundaries, failure handling and audit should be visible and testable.
- Microsoft MCP Gateway: separate control-plane registry/lifecycle from data-plane request routing; deployment lifecycle is part of the product.
- Kuadrant MCP Gateway: enforce auth and network boundaries at gateway/cluster edge; do not rebuild its Envoy/operator/CRD stack for this assignment.

These are design references, not code dependencies. The implementation remains original; the assessment's acceptance tests take priority over feature imitation.
