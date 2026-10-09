# Status (honest, updated 2026-10-09)

Environment of the last session: Python 3.12, Node 22, **no Docker, no Helm, no Kubernetes** available. So everything
Kubernetes/Helm/Docker-related is still UNPROVEN. Everything gateway/MCP/dashboard-build was run for real (output below).

| Gate | State | Evidence |
|---|---|---|
| 0 unit tests | PASS | `pytest tests/gateway` -> 5 passed |
| 0 docker build x5 | NOT RUN | no docker in sandbox: run `./scripts/dev.sh` locally |
| 0 `npm run build` dashboard | PASS | `tsc --noEmit && vite build` clean, 31 modules |
| 0 `helm lint` / `helm template` | NOT RUN | no helm in sandbox: run both locally and paste output |
| 1 WooCommerce on k3d | NOT RUN | wp-setup Job is still the riskiest piece |
| 2 woo-mcp | PASS vs **mock** Woo only | 5 tools exercised via gateway against `test-tools/mockwoo.py`; real WooCommerce REST not tested |
| 3 gateway /mcp | PASS locally | official `mcp` SDK client (`streamablehttp_client`) initialize + list + call OK (protocol 2025-11-25). MCP Inspector / Cursor NOT yet tried by hand |
| 4 three upstreams | PASS locally | 9 tools: `woocommerce__*`(5) `weather__*`(2) `currency__*`(2) |
| 5 members/keys | PASS locally | `tests/integration/control_local.py` 11/11: member key, 403 on admin API, revoke -> 401 |
| 6 dashboard vs gateway | build only | never opened in a browser |
| 7 chat | NOT RUN | needs `ANTHROPIC_API_KEY` |
| 8 failure/control | PASS locally | killed weather-mcp: status `unreachable`, other tools list in 0.03s and call OK; disable hides tools; tool permission hides + rejects direct call |
| 9 k8s hardening | NOT RUN | |
| 10 k3s VPS | NOT RUN | |

## Fixed this session
1. `mcp>=1.9.0` resolved to **mcp 2.3.0** (major rewrite: no `streamablehttp_client`). Pinned `mcp==1.30.0` in all four requirements.txt; verified `streamablehttp_client(url, headers=)` and `FastMCP(host=, port=)` signatures on 1.30.0.
2. Dead-upstream errors surfaced as `ExceptionGroup: unhandled errors in a TaskGroup`; now unwrapped to the root cause (`ConnectError: All connection attempts failed`).

## Local no-k8s loop (what I actually ran)
`test-tools/mockwoo.py` (test-only mock of WooCommerce REST, key `ck_test`/`cs_test`) + 3 MCP servers on 8001-8003 + gateway on 8000
(`WOO` env vars are `WOO_BASE_URL`, `WOO_CONSUMER_KEY`, `WOO_CONSUMER_SECRET`). Then:
`KEY=<admin> python tests/integration/e2e_local.py` and `ADMIN_KEY=<admin> python tests/integration/control_local.py`.

## Still-open known gaps
- Run on your machine next: `docker build` x5, `helm lint`, `helm template`, then `./scripts/dev.sh` (Gate 1).
- woo-mcp has no inbound auth (NetworkPolicy only). Gateway `/mcp` is stateless JSON POST (no GET/SSE): works with the SDK client; still verify with MCP Inspector.
- No Alembic; tool cache per replica; chat history not persisted; dev secrets in values.yaml are placeholders.

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
