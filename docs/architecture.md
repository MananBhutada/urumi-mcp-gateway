# Architecture
Clients (Dashboard, Chat, Cursor, Inspector) → single Gateway (`/mcp`, `/api`) → upstream MCP servers over Streamable HTTP.
Gateway = MCP server (north) + MCP client (south) + control plane (auth, RBAC, registry, routing, audit).
PostgreSQL holds platform data; MySQL holds WooCommerce data (separate domains). Public ingress: storefront + dashboard only
(dashboard nginx proxies `/api`,`/mcp` to the gateway). MCP servers and DBs are cluster-internal.
Request path: authenticate (hash lookup) → authorize (role + tool permission) → start timer → upstream call (timeout) → audit → respond.
