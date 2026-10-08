# Demo script
1. Storefront: store.urumi.local → add Sample Tee → COD checkout → order visible in wp-admin.
2. Dashboard (admin key): servers all 🟢, tools list shows `woocommerce__*`, `weather__*`, `currency__*`.
3. Chat: "Create a product called Test Shirt for 999" → refresh storefront; Audit shows user/server/tool/duration/success.
4. Team: add Member B, mint key. MCP Inspector → http://dashboard.urumi.local/mcp with B's key → tools/list → "orders today?" via chat/tool.
5. Kill test: `kubectl delete pod -l app=weather-mcp` → weather 🔴 within ~15s, woo/currency still work.
6. Revoke B's key → next call 401. 7. Disable weather → tools vanish; re-enable → return.
8. Tool permissions: PUT /api/permissions {"tool":"woocommerce__create_product","allowed":false} → hidden for MEMBER and direct call rejected.
