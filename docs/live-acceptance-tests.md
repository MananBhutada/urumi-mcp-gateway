# Live store and chat acceptance checks

These checks complement unit tests. They do not replace a real browser checkout or a Kubernetes persistence test.

## 1. WooCommerce REST smoke test

Use a dedicated disposable store or local cluster. Create a WooCommerce REST API key with only the required permissions, and do not commit it.

PowerShell example:

\`\`\`powershell
$env:WOO_BASE_URL = "https://store.example.com"
$env:WOO_CONSUMER_KEY = "ck_replace_me"
$env:WOO_CONSUMER_SECRET = "cs_replace_me"
python scripts/smoke_test_woocommerce.py
\`\`\`

For a disposable local-only cluster using HTTP, explicitly opt in:

\`\`\`powershell
$env:WOO_BASE_URL = "http://store.urumi.local"
$env:WOO_ALLOW_INSECURE_HTTP = "1"
python scripts/smoke_test_woocommerce.py
\`\`\`

The script reads products, creates a disposable **draft** product, reads it back, and lists orders. Set \`WOO_TEST_ORDER_ID\` to an existing test order to verify order lookup and a same-status update. It never prints credentials or raw upstream bodies. Delete the disposable draft product manually when finished.

Important: WooCommerce REST credentials are supplied as query parameters by the current client for compatibility with the in-cluster WordPress service. Query parameters can be logged by proxies. Use HTTPS for any non-local environment, keep the service private, redact query strings in logs, and use a least-privilege key.

## 2. Browser checkout acceptance

1. Open the configured storefront host.
2. Verify the Sample Tee or another published test product is visible.
3. Add it to cart and proceed to checkout.
4. Use test-only customer details and Cash on Delivery.
5. Place the order and record the order number/status.
6. Sign into WordPress Admin and verify that order, line items, total and payment method.
7. Restart the WordPress and MySQL pods; verify the product and order still exist.

Do not mark checkout or persistence complete until each step has been performed against the running cluster.

## 3. Gateway MCP acceptance

Connect MCP Inspector or Cursor to the single gateway MCP endpoint using a member API key. Verify initialize, tools/list and tools/call. Confirm WooCommerce tools are namespaced and all calls are audited. Revoke the key and retry: the next call must be rejected. Disable the WooCommerce upstream and refresh tools/list: its tools must disappear and stale calls must fail. Stop the WooCommerce MCP pod and confirm Weather/Currency remain usable.

## 4. Dashboard chat acceptance

The chat API only accepts user/assistant conversation turns, limits the request size, uses server-owned tool schemas, and routes tool calls through the gateway router. Verify a prompt that requires two upstream tools, inspect the tool trace, and confirm the audit records attribute the calls to the logged-in user. If the configured Anthropic key is absent, the chat endpoint should return a safe configuration error rather than pretend the model is running.
