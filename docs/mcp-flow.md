# MCP flow
1. Client POST /mcp `initialize` with `Authorization: Bearer <Urumi Gateway API key>`; the gateway replies with tools capabilities.
2. `tools/list` → union of healthy, enabled upstream tools, prefixed `<server>__`, minus tools denied for the caller's role.
3. `tools/call woocommerce__create_product` → split prefix → permission check → open upstream session (timeout) → call → audit row.
4. Health loop (15s) + on-demand refresh marks upstreams connected/unreachable/disabled.
