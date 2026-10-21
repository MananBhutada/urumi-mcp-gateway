# MCP flow
1. Client POST /mcp `initialize` with `Authorization: Bearer <Urumi Gateway API key>`; the gateway replies with tools capabilities.
2. `tools/list` → union of healthy, enabled upstream tools, prefixed `<server>__`, minus tools denied for the caller's role.
3. `tools/call woocommerce__get_products` or `woocommerce__create_order` → split prefix → require a currently discovered tool → permission check → open upstream session (timeout) → call → audit row.
4. `woocommerce__create_order` requires `test_order=true`; it returns success only after WooCommerce confirms a pending, unpaid order with `_urumi_test_order`. It accepts no customer details. Inspect the store before retrying an unconfirmed POST.
5. Health loop (15s) + on-demand refresh marks upstreams connected/unreachable/disabled.
