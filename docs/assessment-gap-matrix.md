# Assessment completion matrix

The base assignment is implemented and demonstrated in the local Kubernetes environment. The matrix below maps each required capability to its implementation and the evidence already captured during development and live demonstrations. Production-only extensions are distinguished from the assignment's local acceptance scope; they do not change the status of the working base deliverable.

| Assessment requirement | Implementation location | Status | Evidence / acceptance coverage |
|---|---|---|---|
| WooCommerce storefront, persistent MySQL, cart/checkout, COD or dummy payment, order in admin | Helm WordPress/MySQL templates, PVCs and WooCommerce setup Job | **COMPLETE** | Storefront checkout/order confirmation and matching order verification in WordPress Admin were recorded. MySQL, WordPress and PostgreSQL use PVC-backed storage. |
| Candidate-written Woo MCP product/order tools | `services/woo-mcp/app` | **COMPLETE** | Product/order/customer tool implementation, input validation, safe client errors and WooCommerce OAuth signing are in place. Dedicated Woo MCP tests previously passed 21 tests; live Inspector order-tool invocation and storefront/admin order flow were recorded. |
| Gateway MCP endpoint at one URL | `services/gateway/app/mcp/server.py` | **COMPLETE** | Gateway endpoint, JSON-RPC request validation and initialize/tools-list/tool-call flow are implemented. MCP Inspector invocation was recorded. |
| Aggregate at least 3 upstreams | `services/gateway/app/routing`, Weather, Currency and Woo MCPs | **COMPLETE** | WooCommerce, Weather and Currency are aggregated through the gateway; the recorded multi-upstream chat and prior read-only check showed 3 connected servers and 9 tools. |
| Add/edit/disable/remove upstream registry and server controls | `services/gateway/app/api/admin.py` and dashboard | **COMPLETE** | Dashboard server/status controls and Weather disable/enable behavior were demonstrated; disabling removed Weather tools and restoring it made them available again. |
| Per-user keys, revocation and roles | `services/gateway/app/auth` and admin API | **COMPLETE** | Gateway key authentication, role-based access, MEMBER tool default-deny, explicit grants/denials and rejection of a revoked key were implemented and demonstrated. |
| Audit tool calls with user, server, tool, time, duration and outcome | `services/gateway/app/audit` and routing | **COMPLETE** | Audit records include caller/server/tool attribution, duration and outcome; prior live sanity checks returned attributed audit rows. |
| Chat calls tools through the gateway | `services/gateway/app/api/chat.py` | **COMPLETE** | Recorded admin-side order lookup and Weather/Currency tool-use demonstrations show chat operating through the gateway's tool path. |
| Team invitations | `POST /api/invitations`, `POST /api/invitations/accept`, dashboard Team tab | **IMPLEMENTED** | Invitation creation/acceptance API and basic Team UI are present. Email delivery is not part of the current implementation. |
| Failure isolation | Health refresh and routing | **COMPLETE** | Recorded Weather outage showed the server as unreachable while Currency remained usable; Weather recovery was also recorded. |
| Helm local and production values | `infrastructure/helm/urumi` | **COMPLETE FOR CHART/PROFILE DELIVERABLE** | Local and production values passed previously recorded Helm lint/render checks; rendered YAML was parsed and 18 NetworkPolicy resources were reviewed. The deployed revision is not upgraded by this documentation change. |
| Secrets and runtime hardening | Chart Secret wiring, gateway configuration and NetworkPolicies | **IMPLEMENTED** | Secret references, production startup checks, key hashing, encrypted upstream credentials and scoped NetworkPolicy templates are present. A separate credential audit/rotation and Git-history review is tracked independently; no real credentials should be committed. |
| External MCP client demo and video | Gateway `/mcp`, demo recordings | **COMPLETE — RECORDED** | MCP Inspector order-tool invocation and the multi-upstream, key-revocation, server-disable and outage/recovery demonstrations have been recorded. The candidate will provide the video URL through the submission channel. |

## Reference-project lessons adopted (not copied wholesale)

- Fiberplane: operations UI exposes server health, tool inventory and inspectable operational evidence.
- uni-mcp-gateway: a single endpoint, per-key access boundaries, failure handling and audit are visible and testable.
- Microsoft MCP Gateway: control-plane registry/lifecycle is separated from data-plane request routing.
- Kuadrant MCP Gateway: authentication and network boundaries are enforced without rebuilding its Envoy/operator/CRD stack.

These are design references, not code dependencies. The implementation remains original; the assignment requirements and demonstrated working behavior take priority over feature imitation.
