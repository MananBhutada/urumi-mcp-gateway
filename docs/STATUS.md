# Urumi Gateway — current state and evaluator handoff

Updated: 2026-10-21. This is the current summary; dated entries under the historical log are retained for context and may describe earlier revisions. Evidence types are deliberately separated: source review, automated tests, Helm rendering, live demonstrations, and production acceptance are not interchangeable.

## Current verified and demonstrated state

| Area | Current state | Evidence / boundary |
|---|---|---|
| Repository/documentation | Evaluator-facing docs are being updated on a documentation-only branch. | This pass changes only `README.md`, `docs/threat-model.md`, `docs/system-design.md`, and this file. It does not change application code, YAML, Helm values, tests or secrets configuration. |
| Local Kubernetes demo | Core local demo is working and videos have been recorded by the candidate. | Recorded flows include storefront order confirmation and WordPress Admin verification, admin-side chat order lookup, Weather + Currency chat, MCP Inspector order-tool invocation, member-key revocation, dashboard server/status controls, Weather disable/enable and Weather outage isolation with Currency continuing to work. Video files are held separately; no public URL is recorded here. |
| Workload health | Latest user-reported cluster check showed Gateway, Weather MCP, Currency MCP and Woo MCP at 1/1 Ready; the full workload set had previously been observed Running. | This is a point-in-time local-cluster observation, not production availability evidence. |
| WooCommerce flow | Storefront order and Admin-side order verification were demonstrated. | Persistence across pod restarts and a clean-cluster checkout are not claimed by that demo alone. |
| MCP tools and upstreams | WooCommerce, Weather and Currency tool calls were demonstrated through the gateway; MCP Inspector order-tool invocation was recorded. | External client compatibility should be assessed against the running target image and the exact acceptance protocol. |
| Authorization | MEMBER tool permissions default-deny without explicit grants; admin Team UI can grant/deny tools. Key revocation and rejection of the old key were demonstrated. | Keep the live evidence distinct from unit tests; cross-member route-by-route authorization still needs exhaustive acceptance. |
| Failure isolation / operator controls | Weather can be disabled so its tools disappear; a Weather outage is shown as unreachable while Currency remains usable, and Weather can be restored. | This demonstrates the tested local failure scenario, not a complete load/circuit-breaker test. |
| Gateway and Woo MCP tests | Latest recorded local results in the working context: Gateway 22 passed, 1 deselected; Helm tests 2 passed; Woo MCP tests 21 passed. | These results were recorded before this documentation-only pass and were not rerun here. The deselected test uses Python-version-specific behavior; project CI targets Python 3.12. Confirm exact commit/environment before citing results. |
| Dashboard build | Dashboard production build previously passed. | Not rerun during this documentation-only pass. |
| Helm local/prod validation | Both local and production values previously passed Helm lint/render; rendered output parsed and included 18 NetworkPolicy resources. | The latest NetworkPolicy audit found the tracked template to be the valid, more restrictive template. The malformed untracked diff artifact must not be substituted. Results were not rerun during this pass. |
| NetworkPolicy enforcement | The tracked chart contains default-deny/scoped rules, narrow MySQL ingress and database egress denial. | Rendered policy objects are not proof of packet-level enforcement. A live allowed/denied connection test with the target CNI remains open. |
| Persistence | MySQL, WordPress and PostgreSQL use PVC-backed storage; PVCs were previously observed Bound. | A controlled pod-restart persistence check for products/orders has not been established in the current evidence set. Do not delete PVCs. |
| Chat/provider | Local demo videos show chat using WooCommerce order information and Weather/Currency tools. | Provider settings exist, but this summary does not claim production provider reliability or a public deployment. Gateway user keys and provider keys are different. |
| Production/VPS | Production values and a runbook exist. | No completed public VPS/k3s deployment, backup/restore drill or production ingress/TLS acceptance is claimed. |
| Secrets | A separate secrets audit/rotation and Git-history review is planned. | This documentation update does not change values files, rotate credentials, or claim the repository is free of credential risk. The local values overlay has disposable demo values and must not be reused in production. |

## Assignment evaluator summary

### Base requirements

- **Helm/Kubernetes:** single chart, local/prod values, Deployments/Services/Ingress/PVCs/probes/resources, Secret wiring and NetworkPolicy templates are present. Lint/render evidence is recorded above; fresh-cluster deployment and live policy enforcement remain separate gates.
- **Store:** WordPress + WooCommerce and the MySQL persistence resources are present. Storefront checkout/order confirmation and WordPress Admin verification were recorded; pod-restart persistence still needs a controlled test.
- **WooCommerce MCP:** product/order/customer tools and the test-order guard are implemented. MCP Inspector and chat-related order flows were demonstrated; rerun exact acceptance against the target image when preparing the final submission.
- **Gateway:** one endpoint aggregates WooCommerce, Weather and Currency. Multi-upstream calls, tool listing and Weather failure isolation have recorded evidence.
- **Dashboard and access control:** server/status controls, Weather enable/disable, member tool grants and key revocation were demonstrated.
- **Audit/security:** API-key hashing, encrypted upstream credentials, tool-level checks, audit paths and URL validation are implemented in code. These controls need the specific residual-risk tests in `threat-model.md`; implementation is not proof of exhaustive security acceptance.

### Bonus / stand-out items

**Implemented and demonstrated (2):**
1. **Per-tool MEMBER authorization and key revocation:** default-deny behavior, explicit grants/denials and rejection of a revoked key.
2. **Upstream operations and failure isolation:** dashboard server disable/enable, Weather outage detection, continued Currency operation and recovery.

**Implemented, but validation/hardening remains in progress:**
- **NetworkPolicy segmentation:** rules are rendered and structurally checked; live CNI enforcement test remains.
- **SSRF/upstream URL validation:** validation exists, but loopback/DNS-rebinding coverage needs explicit confirmation and possible follow-up.
- **Database-backed shared tool catalog / multiple Gateway replicas:** architecture is implemented; production rollout/session behavior needs live validation.
- **Team invitations:** one-time expiring invitation flow and basic UI exist; email delivery and full browser acceptance remain incomplete.
- **Production operations and secret delivery:** production values and deployment documentation exist; external Secret Manager integration, public VPS/k3s deployment, and backup/restore verification remain incomplete.

Work on the partial bonus items is ongoing. The README and design/security notes intentionally do not label these as production-complete.

## Immediate acceptance items still open

1. Finish the separate secret audit/rotation and Git-history review without exposing values.
2. Verify repository status and that the intended source/documentation commits are synchronized.
3. Re-run the relevant tests and Helm lint/template on the exact submission commit and retain the outputs.
4. Run a controlled persistence check for products/orders after pod restart.
5. Verify live NetworkPolicy allow/deny behavior with the actual cluster CNI.
6. Complete any remaining cross-member/admin authorization checks and review audit attribution for denied calls.
7. Put the already-recorded demo video link(s) in the internship submission form; the repository intentionally does not invent or embed a link that has not been provided.
8. Keep partial bonus work explicitly marked in progress until its own acceptance evidence exists.

## Commands for final verification

Run from the repository root after checking the working tree and confirming the intended commit:

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

These are commands to run, not claimed results of this documentation pass. For cluster-changing commands, use only the intended disposable local cluster and review the plan first.

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
- Not yet verified against MCP Inspector/Cursor, and tests have not been run in this environment. The gateway remains a deliberately stateless JSON-response implementation; live Streamable HTTP client compatibility is still a required assessment gate.


## WooCommerce integration hardening (2026-10-09)

- Product creation now validates and normalizes the name, decimal price, and allowed product status. New products default to `draft`; publishing must be explicit with `status="publish"`.
- Order IDs are validated as positive integers; order response projection tolerates missing billing data and only returns selected fields. Search and description inputs are bounded.
- Woo REST client now validates its configured base URL/path and credentials, applies a configurable bounded timeout, handles connection/timeout/invalid-JSON failures, and does not echo upstream response bodies into tool errors.
- Added isolated regression tests under `tests/woo_mcp` and a separate CI job for them.
- **Not yet verified:** no CI run has been observed for this branch, and this is not proof of a real WooCommerce store or Kubernetes checkout flow. The next acceptance gate remains running CI, then deploying the WordPress/WooCommerce chart and testing REST tools plus a real COD checkout/order in wp-admin.

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
- Live read-only check before this code change showed `/api/servers`, `/api/tools`, and MCP `tools/list` in agreement: 3 connected servers and 9 tools. The historical empty-server anomaly was not reproducible; new shared-session/cache behavior still needs deployment verification.
- MySQL ingress now allows only the WordPress workload and the separately labeled `wp-setup` Job. The broad same-namespace rule was removed. Egress rules allow cluster DNS and the observed database, MCP, WooCommerce setup, chat, Weather, and Currency dependencies; MySQL and PostgreSQL have no egress allowances.
- Verification in the current local Python 3.10 environment: `python -m pytest -q tests/gateway -k 'not root_cause'` -> 22 passed, 1 deselected; `python -m pytest -q tests/helm` -> 2 passed; `python -m pytest -q tests/woo_mcp` -> 21 passed; `npm run build --prefix dashboard` passed; changed Python modules compile. The excluded pre-existing root-cause test uses Python 3.11's built-in `ExceptionGroup`; project CI targets Python 3.12.
- Helm 4.3.0 linted and rendered both local and production values successfully; generated YAML parsed and the 18 NetworkPolicies were checked for ingress sources, internal destinations, HTTPS scope, resolver-only DNS, and database egress denial. CI Helm validation also asserts the scoped MySQL and egress policy resources render. Policy enforcement and live behavior remain unverified until a reviewed build/deployment is performed.
