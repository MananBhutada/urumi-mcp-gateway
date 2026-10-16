# Urumi Gateway — current state and handoff

Updated: 2026-10-16. This section is the current record; dated entries below it
are historical and may describe an earlier state. A passing local build or
render is not evidence of live-store acceptance.

## Current verified state

| Area | State | Evidence / boundary |
|---|---|---|
| Working tree review snapshot | Reviewed for this handoff | At review start, branch `main` matched `origin/main` (0 commits ahead/behind), with 81 status entries and no staged changes. Twenty-seven paths had content diffs; the remaining modified statuses appeared line-ending/metadata-only. The reviewed source, tests, Helm, and documentation changes are intended for synchronization; malformed scratch/output files and an uncertain auth snapshot are excluded. |
| Live local cluster | Running, read-only inspected | Context `k3d-urumi`, namespace `default`; Helm release `urumi` revision 7, `deployed`; gateway and dashboard each showed 1/1 Ready. |
| Dashboard “Invalid key” | Source fix exists; NOT deployed | The browser's sign-in field contained a value that was not a `urumi_live_` Gateway key. The dashboard sent it to `/api/me`; the provider credential is not a Gateway login key. The shared browser's saved `urumi_key` was cleared. The cluster still serves the old dashboard image/UI. |
| Gateway authentication | Live admin auth verified | Gateway container code is under `/srv/app` (image entrypoint `app.main:app`). Without displaying either credential or stored hashes, the configured bootstrap key was compared to the admin's active hashed key; it matched. Authenticated `/api/me` returned HTTP 200 and role `ADMIN`. |
| Bootstrap behavior | Deliberately create-only | `bootstrap()` creates the admin and its key only when the configured email has no user. Changing `BOOTSTRAP_ADMIN_KEY` later does not reconcile or replace an existing key. No reconciliation or database mutation was performed. |
| Python tests | PASS | Gateway and Helm: 53 passed. WooCommerce MCP: 21 passed when run from `services\woo-mcp`. Combined total: 74 passed. |
| Dashboard | PASS locally | From `dashboard`: `npm run build` completed TypeScript checking and Vite production build. Mocked API/key-format assertions passed; no actual dashboard credential was used in these tests. |
| Helm | PASS locally | Local and production lint/render passed with the exact commands below. Both rendered outputs parsed as YAML and contained 18 NetworkPolicies. |
| Kubernetes manifest validation | PASS client-side | `kubectl apply --dry-run=client --validate=true` accepted both rendered profiles. This did not apply resources. |
| Live Helm plan | BLOCKED; no upgrade | A redacted server dry-run against revision 7 proposed changes to 23 resources, including `urumi-secrets`, Gateway Deployment, and NetworkPolicies. The plan was rejected; no upgrade ran. |
| Store / WooCommerce acceptance | PARTIALLY verified | A prior read-only live check listed a WooCommerce product and routed Weather/Currency calls. Fresh checkout, order mutation, and persistence across pod restart remain unverified. |
| LLM provider | Configured in source values; live chat unverified | Local/prod values specify the OpenRouter base URL and model; `llm-api-key` is referenced through `urumi-secrets`. No live chat/model call was made in this investigation. |

### Dashboard authentication finding and safe recovery

`dashboard/src/App.tsx` accepts a **Urumi Gateway API key**, not `LLM_API_KEY`.
`dashboard/src/api.ts` sends the candidate as `Authorization: Bearer ...` to
`GET /api/me`. The gateway hashes that token with HMAC-SHA256 using
`SECRET_KEY`, looks for the hash in `api_keys`, and rejects missing, unknown,
or revoked keys with HTTP 401 (`services/gateway/app/auth/rbac.py`). An
unauthenticated or invalid-key 401 says nothing about OpenRouter authentication.

The fix in the working tree rejects values without the Gateway `urumi_live_`
prefix before sending them, clears malformed saved browser values, persists a
new key only after successful `/api/me`, and distinguishes HTTP 401 from
network/server failures. Regression tests are in
`tests/gateway/test_core.py`. These source edits have **not** reached the live
dashboard image. Use a Gateway key for sign-in; never use a provider key there.

The browser inspection exposed a provider-shaped value in the sign-in field.
It is intentionally not reproduced or committed. Treat the provider credential
as potentially exposed: rotate/revoke it through the provider's secure console
as a security follow-up, then update the Kubernetes Secret only under a
separately approved change plan. No credential rotation has occurred.

## Assignment acceptance and current gaps

| Requirement | Implementation / evidence | Remaining acceptance |
|---|---|---|
| One gateway aggregates WooCommerce, Weather, Currency MCPs | `services/gateway/app/mcp`, `services/gateway/app/routing`; local tests and a prior live tool listing | Verify initialize/list/call with MCP Inspector or another external client against the deployed current image. |
| WooCommerce MCP with product/order tools | `services/woo-mcp/app/tools/products.py` and `orders.py`; `list_products`, `create_product`, `list_orders`, `get_order`, `update_order_status`; mock tests previously passed | Fresh live create/list/get/update against disposable data and verify a real checkout order in WooCommerce. |
| WordPress/WooCommerce and MySQL persistence | Helm WordPress, setup Job, MySQL, and separate PVC templates | Complete checkout and prove product/order/uploads persist after pod restart; document backup/restore separately. |
| Gateway users, keys, roles, permissions, audit | `services/gateway/app/api/admin.py`, `auth/`, `audit/`, `models/tables.py`; 74 focused Gateway/Helm/Woo tests passed | Run acceptance against live current images: member/admin boundaries, revoke behavior, explicit member tool permission, and attributed success/failure audit rows. |
| OpenAI-compatible tool-calling chat | `services/gateway/app/api/chat.py`; settings `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Test a real configured tool-calling model only after deployment/provider approval; require provider support for tool calling. |
| Kubernetes isolation and storage | `infrastructure/helm/urumi/templates/`; 18 rendered NetworkPolicies, separate MySQL/PostgreSQL/WordPress PVCs | A rendered policy is not proof of enforcement. Verify live selectors and traffic in a separately approved acceptance test. |
| CI and portable setup | `.github/workflows/ci.yml`; README and runbooks | CI workflow was not run remotely in this handoff. Fresh clone setup is documented but not freshly exercised. |

## Repository map

| Concern | Paths |
|---|---|
| Gateway API, bootstrap, auth, authorization, keys, invitations, audit | `services/gateway/app/main.py`, `config.py`, `api/`, `auth/`, `models/tables.py`, `routing/`, `audit/` |
| MCP endpoint and upstream transport | `services/gateway/app/mcp/server.py`, `client.py` |
| Chat/provider loop | `services/gateway/app/api/chat.py`, `config.py` |
| WooCommerce tools and REST signing | `services/woo-mcp/app/tools/`, `app/woocommerce.py`, `app/main.py` |
| Dashboard and same-origin API client | `dashboard/src/App.tsx`, `src/api.ts`, `nginx.conf` |
| Kubernetes chart | `infrastructure/helm/urumi/Chart.yaml`, `values.yaml`, `values-local.yaml`, `values-prod.yaml`, `templates/` |
| CI and local helper scripts | `.github/workflows/ci.yml`, `scripts/dev.sh`, `scripts/test.sh`, `scripts/seed.sh` |
| Acceptance docs | `docs/store-deployment-runbook.md`, `live-acceptance-tests.md`, `implementation-checklist.md`, `assessment-gap-matrix.md` |

## Deployment and configuration facts

- One Helm chart is used with shared `values.yaml` plus local or production
  overrides. Local profile is for disposable demo credentials; production
  profile requires unique credentials, PostgreSQL, TLS, and persistent storage.
- The chart renders Deployments for gateway, dashboard and MCP workloads;
  MySQL and PostgreSQL have persistent data claims, and WordPress has a separate
  content claim. The database and MCP services are cluster-internal.
- `templates/secrets.yaml` creates `urumi-secrets`. The gateway obtains
  `SECRET_KEY`, `BOOTSTRAP_ADMIN_KEY`, DB password, and `LLM_API_KEY` via
  `secretKeyRef`; the LLM Secret key is `llm-api-key`. Do not print Secret
  values or store real credentials in values files. Helm release data can
  retain values supplied during installation.
- Local and production profiles currently set `llm.baseUrl` to
  `https://openrouter.ai/api/v1` and `llm.model` to `openrouter/free`. The key
  belongs only in the `urumi-secrets` Secret. The chart currently creates that
  Secret from Helm values; external Secret-manager integration is not present.
- `values-local.yaml` contains explicitly demo-only credentials and must not be
  used against a shared or production cluster. Its reviewed change for this
  handoff only sets the OpenRouter URL/model and changes an empty provider-key
  placeholder; no nonempty credential was added. The credential scan also
  identified the existing local Gateway-key fixture and synthetic test keys;
  none are provider keys. Never copy demo or live credentials into production
  values or publish a live credential.
- NetworkPolicies limit intended ingress and inter-service egress; DNS is
  restricted to the configured cluster resolver, HTTPS egress is limited to
  workloads that need it, and MySQL/PostgreSQL have deny-egress policies. These
  are render assertions, not proof that the live CNI enforces them.
- Admin bootstrap is not a credential rotation mechanism. The configured
  bootstrap key is hashed with `SECRET_KEY` and added only when the admin user
  does not yet exist. Existing users and keys are preserved on later starts.
- There is no Alembic migration workflow. SQLAlchemy `create_all` creates new
  tables at startup, but schema evolution for existing columns needs a planned
  migration process.

## Commands observed for the current working tree

Run from repository root unless noted. Local/prod lint and render were executed
with the shared base values and the relevant overlay:

```powershell
py -3.12 -m pytest -q tests/gateway tests/helm
Push-Location .\services\woo-mcp
py -3.12 -m pytest -q ..\..\tests\woo_mcp
Pop-Location
Set-Location .\dashboard
npm run build
Set-Location ..
helm lint infrastructure/helm/urumi -f infrastructure/helm/urumi/values.yaml -f infrastructure/helm/urumi/values-local.yaml
helm lint infrastructure/helm/urumi -f infrastructure/helm/urumi/values.yaml -f infrastructure/helm/urumi/values-prod.yaml
helm template urumi infrastructure/helm/urumi -f infrastructure/helm/urumi/values.yaml -f infrastructure/helm/urumi/values-local.yaml
helm template urumi infrastructure/helm/urumi -f infrastructure/helm/urumi/values.yaml -f infrastructure/helm/urumi/values-prod.yaml
py -3.12 -m compileall -q services\gateway\app
git diff --check
```

Observed results: 53 Gateway/Helm tests and 21 WooCommerce MCP tests passed;
dashboard build passed; both Helm lint and render pairs passed; rendered YAML
parsed and policy count/provider Secret references were asserted; client-side
Kubernetes dry-run validation passed; Python compile and diff checks passed.
No `helm upgrade`, `kubectl apply` without `--dry-run`, database mutation, or
credential change was performed.

## Cross-computer recovery and deployment gate

The reviewed changes are intended for `main`; the nonstandard untracked
command-output files and uncertain auth snapshot are deliberately excluded.
Do not stage an entire dirty worktree. Before relying on a clean clone, verify
that the reviewed commit is present on `origin/main`. The dashboard source fix
must remain clearly distinguished from the still-undeployed dashboard image.

Do not upgrade Helm from this worktree yet. The dry-run against release revision
7 showed 23 resource changes, including `urumi-secrets` and NetworkPolicies.
First reconcile the deployed values/chart state without exposing secret values,
then produce and review a redacted plan that changes only the intended
dashboard resource and preserves the live Secret and all unrelated resources.
Deployment and provider-key rotation each require separate approval.

On a second Windows computer, once an approved commit has been pushed:

```powershell
git clone https://github.com/MananBhutada/urumi-mcp-gateway.git
Set-Location .\urumi-mcp-gateway
git switch main
git pull --ff-only origin main
git status --short
```

For an existing clean clone, use `git pull --ff-only origin main`. If it has
local changes, inspect and preserve them before pulling; do not reset or
overwrite another computer's work.

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
