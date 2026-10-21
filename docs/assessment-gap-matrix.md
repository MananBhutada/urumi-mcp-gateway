# Assessment gap matrix



| Assessment requirement | Implementation location | Current confidence | Acceptance proof still required |
|---|---|---|---|
| WooCommerce storefront, persistent MySQL, cart/checkout, COD or dummy payment, order in admin | Helm WordPress/MySQL templates and WooCommerce setup job | Unverified in Kubernetes | Fresh k3d install; place COD order; verify in wp-admin; restart pods and verify persistence |
| Candidate-written Woo MCP with 5 required product/order tools | services/woo-mcp/app | Tool input validation and safe client errors added; real-store behavior still unverified | Pass the dedicated Woo-MCP CI job; test against real WooCommerce; verify create/list product, list/get/update order, then complete a COD storefront checkout and confirm it in wp-admin |
| Gateway MCP endpoint at one URL | services/gateway/app/mcp/server.py | JSON-RPC validation tests and prior SDK initialize/list/call evidence; implementation is stateless JSON response without SSE; external-client compatibility remains unverified | Run MCP Inspector or Cursor against /mcp; verify initialize, tools/list, tools/call, notifications, malformed JSON-RPC, protocol-version mismatch and auth failures |
| Aggregate at least 3 upstreams | services/gateway/app/routing and weather/currency/Woo MCPs | 9 tools reported in local test | Re-run scripted cross-upstream calls; prove namespace collision handling |
| Add/edit/disable/remove upstream registry | services/gateway/app/api/admin.py and dashboard | Backend operations exist; dashboard edit UX incomplete | Browser-test every control; disabled tools disappear promptly and stale cache cannot call disabled server |
| Per-user keys, revocation, roles | services/gateway/app/auth and admin API | Local tests previously recorded | External client key works; revoke then next call returns 401; non-admin receives 403 on all admin routes |
| Audit each tool call with user, server, tool, time, duration and outcome | services/gateway/app/audit and routing | Code exists; failure semantics need testing | Success and error each produce exactly one attributed row; verify chat and external MCP source |
| Chat calls tools only through gateway | services/gateway/app/api/chat.py | Code exists; live model integration untested | Prove chat cannot call upstream directly; prompt requires tools from Woo plus Weather or Currency |
| Team invitations | POST /api/invitations, POST /api/invitations/accept, dashboard Team tab | API and basic create/accept UI implemented in this branch; email delivery absent | Browser-test invite creation, fragment link, expired/reused token rejection and first-login API key flow |
| Failure isolation | Health refresh and routing | Local Weather-MCP stop test previously recorded | Kill one pod in Kubernetes; its tools become unavailable while the other two continue answering |
| Helm local and production values | infrastructure/helm/urumi | Local lint/render passed for both profiles; rendered YAML parsed and client-side manifest validation passed | Reconcile deployed Helm revision 7 with the current chart and review a redacted resource plan before any upgrade |
| Secrets and runtime hardening | chart secrets, gateway config and NetworkPolicies | Partially hardened in this branch | Confirm no live credentials are committed, weak production config fails startup, and upstream/DB have no public ingress |
| External MCP client demo and video | docs/demo-script.md | Not yet proven | Record one endpoint/key, multi-upstream call, key revocation, server disable and one-upstream outage |

## Reference-project lessons adopted (not copied wholesale)

- Fiberplane: operations UI should expose server editing/health, tool inventory and inspectable audit/traffic evidence.
- uni-mcp-gateway: single endpoint, per-key access boundaries, failure handling and audit should be visible and testable.
- Microsoft MCP Gateway: separate control-plane registry/lifecycle from data-plane request routing; deployment lifecycle is part of the product.
- Kuadrant MCP Gateway: enforce auth and network boundaries at gateway/cluster edge; do not rebuild its Envoy/operator/CRD stack for this assignment.

These are design references, not code dependencies. The implementation remains original; the assessment's acceptance tests take priority over feature imitation.
