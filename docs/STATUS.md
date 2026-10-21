# Urumi Gateway — current state and evaluator handoff

Updated: 2026-10-21. This is the current summary; dated entries under the historical log are retained for context and may describe earlier revisions. Evidence types are deliberately separated: source review, automated tests, Helm rendering, live demonstrations, and production acceptance are not interchangeable.

## Completed assignment status

The base Urumi AI FDE assignment is implemented and demonstrated in the local Kubernetes environment. The documentation-only branch updates evaluator-facing descriptions and does not change application code, chart YAML, values, tests or secrets.

| Area | Status | Evidence |
|---|---|---|
| Local Kubernetes deployment | **COMPLETE / DEMONSTRATED** | Recorded local-cluster videos cover the core application flows and operations controls. |
| WooCommerce storefront and orders | **COMPLETE / DEMONSTRATED** | Storefront order confirmation and matching WordPress Admin verification were recorded. |
| WooCommerce MCP | **COMPLETE** | Product/order/customer tools, input validation, safe client errors and OAuth signing are implemented. Woo MCP tests previously recorded 21 passing tests; MCP Inspector order-tool invocation was recorded. |
| Gateway and upstream aggregation | **COMPLETE / DEMONSTRATED** | WooCommerce, Weather and Currency are routed through one gateway. Prior read-only checks reported 3 connected servers and 9 tools; multi-upstream chat was recorded. |
| Dashboard and operator controls | **COMPLETE / DEMONSTRATED** | Server status, Weather disable/enable, outage detection, continued Currency operation and recovery were recorded. |
| Authentication and permissions | **COMPLETE / DEMONSTRATED** | Gateway API keys, admin/member roles, default-deny member tool permissions, explicit grants/denials and revoked-key rejection are implemented; revocation was recorded. |
| Audit | **IMPLEMENTED** | Audit rows carry user/server/tool attribution, duration and outcome; prior live checks returned attributed rows. |
| Helm chart | **COMPLETE FOR ASSIGNMENT CHART SCOPE** | Local and production values previously passed Helm lint/render; rendered YAML was parsed and 18 NetworkPolicy resources were reviewed. |
| Tests and dashboard build | **PREVIOUSLY PASSED** | Gateway: 22 passed, 1 deselected; Helm: 2 passed; Woo MCP: 21 passed; dashboard build passed in the previously recorded environment. These are historical results, not a claim that this documentation-only change reran them. |
| Network segmentation | **IMPLEMENTED IN CHART** | Scoped/default-deny rules, narrow MySQL ingress and database egress denial are present. Target-cluster packet enforcement depends on the configured CNI. |
| Team invitations | **IMPLEMENTED** | One-time invitation API and basic Team UI are present; email delivery is not part of this implementation. |
| Production deployment profile | **PROVIDED** | Production values and a deployment runbook are included; target-specific DNS/TLS/storage/secret injection are configured at deployment time. |
| Credential handling | **IMPLEMENTED WITH SEPARATE AUDIT TASK** | Secret wiring and runtime controls exist. The planned credential audit/rotation and Git-history review is separate; do not commit or expose real credentials. |

## Evaluator summary

The base assignment is complete in the demonstrated local Kubernetes scope: WordPress/WooCommerce, persistent database resources, the Woo MCP server, one gateway endpoint aggregating three upstreams, dashboard/chat, API-key and role controls, tool permissions, audit paths, Helm packaging and the recorded operational demonstrations are in place.

Additional engineering includes member tool-level access control and key revocation, upstream disable/recovery and failure isolation, scoped NetworkPolicy templates, database-backed tool catalog, and invitation API/UI. Deployment-specific hardening (for example external secret-manager integration, a public VPS deployment and backup/restore configuration) is distinct from the local assignment deliverable.

## Submission evidence

The candidate has already recorded videos showing:
- WooCommerce storefront checkout/order confirmation and WordPress Admin verification.
- Admin-side chat order lookup and Weather/Currency tool use.
- MCP Inspector order-tool invocation.
- Member key revocation and rejection of the revoked key.
- Dashboard server/status controls and Weather enable/disable.
- Weather outage isolation while Currency remains usable, followed by recovery.
- Kubernetes workload health.

The videos are held separately; add the appropriate existing video link(s) to the internship submission form. Do not invent a public URL.

## Final handoff checklist

- Confirm the intended documentation branch/commit is the version to submit.
- Keep the separately planned credential audit/rotation and Git-history review isolated from ordinary documentation changes.
- Attach the existing demo video link(s) in the submission form.
- If deploying to a different cluster or public VPS, apply the target-specific DNS/TLS/storage/secret settings and validate the target environment.

## Commands for optional reproducible re-checks

Run from the repository root after confirming the intended commit:

```powershell
git status --short
git log -1 --oneline
python -m pytest -q tests/gateway
python -m pytest -q tests/helm
python -m pytest -q tests/woo_mcp
npm run build --prefix dashboard
helm lint infrastructure/helm/urumi -f infrastructure/helm/urumi/values-local.yaml
helm template urumi infrastructure/helm/urumi -f infrastructure/helm/urumi/values-local.yaml
helm lint infrastructure/helm/urumi -f infrastructure/helm/urumi/values-prod.yaml
helm template urumi infrastructure/helm/urumi -f infrastructure/helm/urumi/values-prod.yaml
```

These commands are reproducibility checks; they are not required to interpret the recorded results above.

## Historical execution log



Entries below are retained as history. Their results are not substitutes for
the current table or for acceptance on the current live images.

## Session 3 (2026-10-09, sandbox: Python 3.12, Node 22; NO docker/helm/kubectl/k3d; helm download blocked)
Note: the uploaded zip contained **no `.git` directory**, so no commits were made. Changes are listed below for you to commit in your real repo.

**Item 2 DONE (woo-mcp inbound auth), verified locally, Helm wiring NOT verified (no helm):**
- `services/woo-mcp/app/main.py`: ASGI `BearerAuth` middleware (constant-time compare) around `mcp.streamable_http_app()`; reads `MCP_AUTH_TOKEN`;
  refuses to start without it unless `MCP_ALLOW_NO_AUTH=1` (fail closed).
- `services/gateway/app/main.py`: seed entries accept `credential_env` (name of an env var holding the upstream credential) so the token never sits in the JSON.
- Helm: `mcp-servers.yaml` sets `MCP_AUTH_TOKEN` from secret `woo-mcp-token`; `gateway.yaml` sets `WOO_MCP_TOKEN` and seeds `credential_env`.
- Real output: direct to woo-mcp with no token -> 401, bad token -> 401, good token -> 200; no `MCP_AUTH_TOKEN` -> `SystemExit: MCP_AUTH_TOKEN is required`.
  Full loop (mockwoo via `uvicorn mockwoo:app --port 9999`, 3 MCP servers, gateway with `credential_env`): e2e_local.py -> 9 tools, create_product + list_orders OK, unknown tool clean isError.
  `pytest tests/gateway` -> 5 passed.
- Item 5 partial: `GET /mcp` on the gateway returns **405** (good). Inspector/Cursor/Claude Code still untested.
- Remember: weather/currency servers still have no inbound auth (NetworkPolicy only); mockwoo is run with uvicorn, not `python mockwoo.py`.


## Hardening branch changes (2026-10-09; not yet locally executed)

- Upstream URL validation now runs at registration, periodic health refresh and immediately before a tool call. This is defense in depth, not a full SSRF solution: in-cluster DNS is allowed, so production egress/network policy and hostname allowlisting remain important.
- Production startup checks reject weak/default gateway secrets, weak bootstrap admin keys and SQLite.
- Helm passes APP_ENV explicitly; production values enable the strict checks. Shared values.yaml no longer has reusable credentials; disposable values are in values-local.yaml.
- Team invitation API and basic dashboard UI added: admin creates a seven-day token and copyable fragment link; acceptance is one-time and creates a member/admin account plus an API key returned once. Email delivery is still missing.
- Added test coverage for URL validation, production config checks and invitation acceptance.
- Added docs/assessment-gap-matrix.md as the rubric-to-evidence tracker.

**Important:** These are changes committed on branch hardening/assessment-gaps. They have not been executed in this environment. Re-run pytest tests/gateway, helm lint, helm template for local and production values, then perform the real k3d/storefront and external MCP-client gates before treating them as verified.


## MCP protocol boundary hardening (2026-10-09)

- The gateway MCP endpoint now validates JSON-RPC envelopes and reports parse errors (-32700), invalid requests (-32600), unknown methods (-32601), and invalid tool-call parameters (-32602) instead of allowing malformed input to bubble into server errors.
- Initialization responds with a supported protocol version; common MCP notifications are acknowledged without JSON-RPC response bodies.
- Regression tests cover request shape, parse errors, unsupported methods and malformed tool-call parameters.
- Outside the validation scope of that historical session against MCP Inspector/Cursor, and tests have not been run in this environment. The gateway remains a deliberately stateless JSON-response implementation; live Streamable HTTP client compatibility is still a required assessment gate.


## WooCommerce integration hardening (2026-10-09)

- Product creation now validates and normalizes the name, decimal price, and allowed product status. New products default to `draft`; publishing must be explicit with `status="publish"`.
- Order IDs are validated as positive integers; order response projection tolerates missing billing data and only returns selected fields. Search and description inputs are bounded.
- Woo REST client now validates its configured base URL/path and credentials, applies a configurable bounded timeout, handles connection/timeout/invalid-JSON failures, and does not echo upstream response bodies into tool errors.
- Added isolated regression tests under `tests/woo_mcp` and a separate CI job for them.
- **Outside the validation scope of that historical session:** no CI run has been observed for this branch, and this is not proof of a real WooCommerce store or Kubernetes checkout flow. The next acceptance gate remains running CI, then deploying the WordPress/WooCommerce chart and testing REST tools plus a real COD checkout/order in wp-admin.

## Live k3d recovery verification (2026-10-13)

- Fixed WooCommerce REST 401 for the in-cluster HTTP path by replacing query-parameter `consumer_key`/`consumer_secret` auth with WooCommerce-compatible OAuth 1.0a signing. The request still goes to `http://wordpress`; the signature uses the canonical `store.urumi.local` host when `WOO_HOST_HEADER` is set.
- Built and imported `urumi/woo-mcp:latest`, restarted `deployment/woo-mcp`, and verified the running container has the OAuth signer.
- Live read-only product listing from inside `woo-mcp` returned `OK list 1`.
- Gateway MCP `tools/list` returned 9 tools including `woocommerce__list_products`; gateway-routed `woocommerce__list_products`, `weather__get_weather`, and `currency__convert_currency` all returned `isError False`.
- Fixed currency acceptance by allowing redirects from Frankfurter's old `.app/latest` endpoint to its current `.dev/v1/latest` endpoint; built/imported/restarted `currency-mcp`.
- Auth/audit sanity check: admin `tools/list` returned HTTP 200, a bad bearer key returned HTTP 401, and `/api/audit?limit=5` returned rows with `user`, `server`, `tool`, `duration_ms`, and `success`.
- Unit checks run locally: `python -m pytest tests\woo_mcp` -> 21 passed; `python -m py_compile services\woo-mcp\app\woocommerce.py`; `python -m py_compile services\currency-mcp\app\main.py`.
- Still not run in this session: Helm lint/template, dashboard build, real browser checkout, order mutation, external MCP Inspector/Cursor, and chat/model flow.

## Authorization, catalog consistency, and policy hardening (2026-10-16)

- Member tool permissions now default-deny when no role/tool row exists; admins retain access to every tool. Added tests for listing and direct-call denial, including audit and no-upstream-call behavior.
- The Team dashboard now lists the current tools and lets admins explicitly grant or deny each tool for the MEMBER role. `tests/integration/control_local.py` now checks both implicit denial and an explicit grant.
- The gateway tool catalog is stored in the existing PostgreSQL/SQLite database and filtered through the same request DB session as `/api/servers`, `/api/tools`, MCP `tools/list`, and chat. This makes the catalog shared across gateway replicas. The new table is created by the existing SQLAlchemy bootstrap.
- Live read-only check before this code change showed `/api/servers`, `/api/tools`, and MCP `tools/list` in agreement: 3 connected servers and 9 tools. The historical empty-server anomaly was not reproducible; new shared-session/cache behavior was scheduled for deployment verification after that historical change.
- MySQL ingress now allows only the WordPress workload and the separately labeled `wp-setup` Job. The broad same-namespace rule was removed. Egress rules allow cluster DNS and the observed database, MCP, WooCommerce setup, chat, Weather, and Currency dependencies; MySQL and PostgreSQL have no egress allowances.
- Verification in the current local Python 3.10 environment: `python -m pytest -q tests/gateway -k 'not root_cause'` -> 22 passed, 1 deselected; `python -m pytest -q tests/helm` -> 2 passed; `python -m pytest -q tests/woo_mcp` -> 21 passed; `npm run build --prefix dashboard` passed; changed Python modules compile. The excluded pre-existing root-cause test uses Python 3.11's built-in `ExceptionGroup`; project CI targets Python 3.12.
- Helm 4.3.0 linted and rendered both local and production values successfully; generated YAML parsed and the 18 NetworkPolicies were checked for ingress sources, internal destinations, HTTPS scope, resolver-only DNS, and database egress denial. CI Helm validation also asserts the scoped MySQL and egress policy resources render. Policy enforcement and live behavior remain not covered by that historical validation until a reviewed build/deployment is performed.
