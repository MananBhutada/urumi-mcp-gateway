# Implementation checklist — Urumi MCP Gateway

Use this as the single working acceptance checklist. Mark an item complete only after the stated proof exists; code presence alone is not evidence. Keep this file current as the implementation and demo evolve.

## A. Kubernetes and Helm foundation
- [ ] Local Kind/k3d cluster can be created from documented commands.
- [ ] The same Helm chart renders with `values-local.yaml` and `values-prod.yaml`.
- [ ] `helm lint` and `helm template` pass for both environments.
- [ ] Every application image has a documented build/tag path; avoid mutable `latest` for production.
- [ ] Deployments/StatefulSets have resource requests/limits and readiness/liveness probes.
- [ ] Ingress exposes only the dashboard and storefront; no database or upstream MCP has public Ingress.
- [ ] NetworkPolicies restrict database and MCP traffic to required callers.
- [ ] Production uses TLS, unique secrets and persistent storage.

## B. WordPress + WooCommerce storefront
- [ ] Fresh install creates WordPress and activates WooCommerce without manual shell intervention.
- [ ] Admin bootstrap is idempotent; rerunning setup does not duplicate products, keys or pages.
- [ ] WooCommerce store currency is INR and COD is enabled.
- [ ] Storefront has at least one purchasable, published test product.
- [ ] Product detail page, cart and checkout load through the store Ingress.
- [ ] Complete a test checkout using COD (or a documented dummy gateway).
- [ ] Confirm the resulting order appears in WooCommerce Admin with the expected line items and status.
- [ ] Restart WordPress and MySQL pods; confirm products, orders and uploaded content persist.
- [ ] WordPress files and MySQL data use separate PVCs; backup/restore procedure is documented.
- [ ] WooCommerce REST API key is least-privilege for the needed operations and stored as a Kubernetes Secret.
- [ ] REST credentials are never included in logs, tool responses, Git commits or public URLs.
- [ ] Store host, WordPress canonical URL and forwarded HTTPS handling agree with the selected local/production values.

## C. Candidate-written WooCommerce MCP
- [ ] MCP uses the required HTTP transport and is reachable only inside the cluster.
- [ ] `list_products` works against the deployed store.
- [ ] `create_product` validates inputs and defaults to draft.
- [ ] `list_orders` works against real checkout orders.
- [ ] `get_order` returns the selected order.
- [ ] `update_order_status` changes the selected order and the change appears in wp-admin.
- [ ] Invalid IDs, prices, statuses, upstream timeout and HTTP errors return safe errors.
- [ ] Test suite passes in CI and includes mocked error cases plus live-store smoke-test instructions.

## D. Gateway MCP contract
- [ ] One stable gateway endpoint exposes aggregated tools using Streamable HTTP.
- [ ] Initialization, `tools/list`, `tools/call`, ping and notifications work with MCP Inspector or Cursor.
- [ ] Invalid JSON-RPC, unknown methods, invalid arguments and unauthenticated calls return appropriate errors.
- [ ] Tool names are collision-safe and identify their upstream server.
- [ ] External client can call WooCommerce, Weather and Currency tools through the same endpoint.
- [ ] Dashboard chat invokes tools only through the gateway, never directly against upstream MCP servers.

## E. Authentication, authorization and audit
- [ ] Admin and member roles are enforced server-side on all admin endpoints.
- [ ] Each member API key is generated securely, shown once, stored hashed and revocable.
- [ ] Revoking a key makes its next request fail.
- [ ] Members can call only explicitly allowed tools; missing permission rows do not silently grant access.
- [ ] Every successful and failed tool call produces one audit event with user, upstream, tool, timestamp, duration and outcome.
- [ ] Chat-originated calls are attributed to the logged-in user.
- [ ] Invitation tokens are one-time, expire, and cannot be reused.
- [ ] Logs and API errors do not leak credentials, secrets, raw upstream bodies or unnecessary customer PII.

## F. Registry and resilience
- [ ] Admin can add, edit, disable and remove an upstream MCP server.
- [ ] Disabling a server removes its tools from discovery and rejects stale calls.
- [ ] Health state and last error are visible in the dashboard.
- [ ] Stop one upstream pod; its tools fail clearly while other upstreams continue to work.
- [ ] Timeouts and failures are audited; retries do not duplicate unsafe write operations.
- [ ] SSRF controls reject loopback, link-local, private or otherwise disallowed upstream destinations as appropriate to deployment policy.

## G. Dashboard and chat
- [ ] Dashboard can manage upstreams, users/API keys, permissions and invitations.
- [ ] Tool registry and server health reflect backend state, not hardcoded demo data.
- [ ] Audit log can be filtered/read by authorized admins.
- [ ] Chat can use at least two upstreams in one prompt and shows tool activity.
- [ ] Chat failures are recoverable and do not bypass gateway authorization.

## H. Deployment, evidence and submission
- [ ] CI runs gateway tests, Woo MCP tests and dashboard build on the intended branches/PRs.
- [ ] Both local and production Helm configurations render and are reviewed.
- [ ] Local cluster deployment succeeds from a clean state.
- [ ] Production-like VPS/k3s deployment uses the same chart and production values.
- [ ] External MCP client demo proves single endpoint, multi-upstream calls, key revocation, server disable and upstream outage isolation.
- [ ] README documents setup, secrets, architecture, threat model, tradeoffs, troubleshooting and cleanup.
- [ ] Demo video shows the actual running implementation and its evidence.
- [ ] Final walkthrough can explain each trust boundary, secret, persistent volume and failure mode.

## Current priority order
1. Validate Helm/WordPress setup and close the real storefront + persistence gate.
2. Run CI and fix failures before merging code changes.
3. Smoke-test the five WooCommerce MCP tools against the deployed store.
4. Prove the gateway protocol and external-client compatibility.
5. Close per-tool authorization and audit semantics.
6. Demonstrate failure isolation and complete the submission evidence.
