# System design and production considerations

## Purpose and request path

Urumi exposes one Streamable HTTP MCP endpoint at `/mcp`. A client authenticates with a Urumi Gateway API key; the gateway resolves the requested namespaced tool, checks the user's role/tool permissions, calls the configured upstream MCP server with server-side credentials, records the outcome, and returns the result. The chat agent uses the same gateway routing and authorization boundary rather than calling upstreams directly.

The upstreams are:

- **WooCommerce MCP** — validated product/order/customer operations through the WooCommerce REST API.
- **Weather MCP** — weather and forecast tools.
- **Currency MCP** — currency conversion tools.

WordPress/WooCommerce uses MySQL and persistent storage. PostgreSQL stores Gateway users, API-key hashes, server/tool catalog state, permissions, invitations and audit data. The dashboard is a React + TypeScript application and communicates with the Gateway API.

## Main components

| Component | Responsibility | Important boundary |
|---|---|---|
| Gateway API and MCP endpoint | Authentication, routing, RBAC, chat, health and audit | Single policy enforcement point for client calls |
| Upstream MCP services | Expose domain tools | Internal services; Gateway is the intended caller |
| WooCommerce REST integration | Read/write store data | Does not query the commerce database directly |
| Dashboard | Operator UI, Team controls and chat | Gateway key is distinct from provider key |
| PostgreSQL | User, key-hash, catalog, permission, invitation and audit records | PVC-backed; backups and migrations are operational responsibilities |
| MySQL + WordPress | Storefront, products and orders | MySQL ingress should be limited to WordPress and the setup Job |
| Helm + Kubernetes | Workloads, Services, Ingress, PVCs, Secrets and NetworkPolicies | Rendered manifests require live enforcement validation |

## Data and access design

- Gateway API keys are displayed once and stored as HMAC-SHA256 hashes.
- Stored upstream credentials are Fernet-encrypted at rest; credential management is server-side.
- Admin routes require admin authorization. MEMBER tool permissions default-deny unless explicitly granted.
- Tool permissions are enforced during tool discovery and direct execution.
- Tool names are namespaced by upstream to avoid collisions.
- Upstream calls use bounded connection/call timeouts and per-call sessions to reduce failure coupling.
- Audit records capture the actor and tool outcome, subject to the current implementation's audit fields.
- The shared tool catalog is database-backed so Gateway replicas can read consistent catalog state.

## Trade-offs and limitations

- SQLAlchemy access is synchronous in async handlers; this is simple but can constrain throughput under load.
- The MCP endpoint currently returns stateless JSON responses and does not implement an SSE session. Confirm compatibility with the evaluator's target client rather than assuming every Streamable HTTP client will accept the same behavior.
- There is no Alembic migration workflow. Additive startup table creation is not a replacement for versioned migrations, rollback planning or schema compatibility testing.
- Invitation acceptance is implemented, but automated email delivery is not.
- URL validation is defense in depth. In-cluster DNS is required, loopback coverage is not yet established as complete, and production egress policy/hostname allowlisting remain important.
- NetworkPolicy templates have been linted/rendered and structurally checked; live allowed/denied traffic and CNI enforcement still need a recorded test.
- The chart creates Secret content from Helm values. Helm release data may retain those values, so this is not equivalent to a fully integrated external Secret Manager.
- Two Gateway replicas in the production profile do not by themselves prove production readiness. Verify shared database behavior, rolling updates, health checks, concurrency and session/client compatibility under replica changes.

## What changes for production (VPS / k3s)

### DNS and ingress

1. Point the chosen public DNS names at the VPS/load balancer and configure the cluster ingress controller.
2. Replace local hostnames with real domains in the production values.
3. Enable HTTPS and configure a valid TLS Secret referenced by the Ingress. Verify certificate renewal and HTTP-to-HTTPS behavior.
4. Expose only the dashboard/store ingress that is intentionally public. Keep Gateway MCP, databases and upstream MCP Services internal unless a reviewed design explicitly requires otherwise.
5. Test ingress source restrictions and NetworkPolicies on the actual cluster CNI.

### Storage and recovery

1. Choose a StorageClass suitable for the VPS and its failure model. The sample `local-path` class is node-local; it is not replicated storage and may not survive node loss.
2. Size MySQL, WordPress and PostgreSQL PVCs for the expected workload.
3. Define scheduled backups, off-node backup storage, restore drills, retention and recovery objectives.
4. Test product/order and user/audit persistence after safe pod restarts. Do not delete PVCs as a persistence test.
5. Add a versioned migration plan before making schema changes that cannot be safely handled by additive table creation.

### Secrets and identity

1. Generate unique production values for Gateway signing/encryption, bootstrap admin, database, WordPress and WooCommerce credentials.
2. Prefer a managed secret integration or a protected deployment-time injection workflow. The current chart creates Kubernetes Secrets from Helm values; do not assume that a Kubernetes Secret object prevents values from being retained in Helm release data.
3. Never commit populated production values, print credentials in logs, pass secrets in shell history, or use local demo credentials in production.
4. Establish key rotation, backup/encryption-key recovery and incident-response procedures. Review Git history for any real credential exposure before public submission/deployment.
5. Keep the LLM-provider credential separate from Gateway user API keys and restrict its provider/model permissions where available.

### Runtime, availability and observability

- Publish immutable image tags and define a repeatable build/rollback process.
- Review resource requests/limits, probes, non-root settings, pod security, replica count and rolling-update strategy.
- Verify database connectivity and catalog consistency during Gateway replica rollouts.
- Add operational monitoring, structured redacted logs, alerting, rate limits and concurrency controls appropriate to the deployment.
- Validate NetworkPolicies with actual allowed and denied connections, not only YAML rendering.
- Run the live acceptance suite after deployment and retain evidence for checkout, order verification, permissions, audit, outage isolation and persistence.

## Evidence boundary

The project has recorded local-cluster demonstrations for checkout/order verification, chat/tool use, MCP Inspector, member key revocation, dashboard controls and Weather failure isolation. Automated test and Helm results are summarized in [STATUS.md](STATUS.md). These support the local assignment demo; they do not establish a completed public VPS deployment, external Secret Manager integration, backup/restore readiness or exhaustive security testing.
