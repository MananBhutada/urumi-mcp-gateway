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

Important: the Woo MCP client signs WooCommerce REST requests with OAuth 1.0a. For local HTTP clusters, it sends the request to the in-cluster WordPress service while signing the canonical store host URL. Keep the service private, redact query strings in logs, and use a least-privilege key.

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

The chat API only accepts user/assistant conversation turns, limits the request size, uses server-owned tool schemas, and routes tool calls through the gateway router. Verify a prompt that requires two upstream tools, inspect the tool trace, and confirm the audit records attribute the calls to the logged-in user. If LLM configuration is missing or a provider request fails, the chat endpoint should return a safe error rather than pretend the model is running.

The provider is configured through `LLM_BASE_URL`, `LLM_MODEL`, and
`LLM_API_KEY` using an OpenAI-compatible chat-completions API. The selected
provider/model must support tool calling. Provider credentials are not
dashboard login credentials: dashboard sign-in and `/api/me` require a
Urumi Gateway API key. A `/api/me` 401 does not indicate an LLM provider error.
For the latest verified source/live distinction and outstanding deployment
blocker, see [STATUS.md](STATUS.md).

## 5. Ordered final demo and acceptance sequence

The source changes must first be deployed to a **disposable local cluster**.
`scripts/dev.sh` builds images and runs `helm upgrade --install`; do not run it
against a shared or production cluster. For an existing local release it checks
the k3d context, warns about possible Secret/NetworkPolicy/workload changes,
and requires an interactive exact confirmation; this is not a substitute for
reviewing a redacted plan. The script accepts `LLM_API_KEY` from the protected
launching environment. Helm stores chart values in release data. No live
deployment or live acceptance is claimed by these instructions.

1. **Open the services.** Browse to `http://store.urumi.local` and
   `http://dashboard.urumi.local`. Confirm both load.
2. **Sign in.** Use the Urumi Gateway admin API key, never `LLM_API_KEY` or a
   WooCommerce REST key. Use the key already held securely.
3. **Verify provider chat.** Ask the dashboard chat to describe a current
   product. Confirm the configured model supports tool calling and the response
   shows a tool trace. Never paste credentials into chat.
4. **Discover the servers and tools.** In PowerShell, set
   `$env:URUMI_GATEWAY_API_KEY` from your secure credential store. Then run:

   ```powershell
   $base = "http://dashboard.urumi.local"
   $gatewayKey = $env:URUMI_GATEWAY_API_KEY
   if ([string]::IsNullOrWhiteSpace($gatewayKey)) { throw "Set URUMI_GATEWAY_API_KEY in this protected session first." }
   $headers = @{ Authorization = "Bearer $gatewayKey" }
   Invoke-RestMethod "$base/api/me" -Headers $headers
   Invoke-RestMethod "$base/api/servers" -Headers $headers
   Invoke-RestMethod "$base/api/tools" -Headers $headers

   function Invoke-UrumiMcp {
     param(
       [string]$RpcMethod,
       [hashtable]$Params = @{},
       [string]$ApiKey = $env:URUMI_GATEWAY_API_KEY
     )
     $rpcHeaders = @{ Authorization = "Bearer $ApiKey" }
     $body = @{
       jsonrpc = "2.0"
       id = [guid]::NewGuid().ToString()
       method = $RpcMethod
       params = $Params
     } | ConvertTo-Json -Depth 20
     Invoke-RestMethod "$base/mcp" -Method Post -Headers $rpcHeaders `
       -ContentType "application/json" -Body $body
   }

   Invoke-UrumiMcp -RpcMethod "initialize" -Params @{
     protocolVersion = "2025-03-26"; capabilities = @{}
     clientInfo = @{ name = "urumi-live-acceptance"; version = "1.0" }
   }
   $toolList = Invoke-UrumiMcp -RpcMethod "tools/list"
   $toolList.result.tools | Select-Object -ExpandProperty name
   ```

   Confirm WooCommerce, Weather, and Currency tools are listed. `tools/list`
   reflects the authenticated user's grants.
5. **Read store data.** Run the following calls. For customer lookup, obtain
   the ID of a test-only customer from WooCommerce Admin:

   ```powershell
   $productsCall = Invoke-UrumiMcp -RpcMethod "tools/call" -Params @{
     name = "woocommerce__get_products"; arguments = @{ per_page = 10 }
   }
   $productsCall.result.content[0].text
   $ordersCall = Invoke-UrumiMcp -RpcMethod "tools/call" -Params @{
     name = "woocommerce__get_orders"; arguments = @{ per_page = 10 }
   }
   $ordersCall.result.content[0].text
   $customerId = [int](Read-Host "Enter the test-only WooCommerce customer ID")
   Invoke-UrumiMcp -RpcMethod "tools/call" -Params @{
     name = "woocommerce__get_customer"; arguments = @{ customer_id = $customerId }
   }
   ```

   Customer results omit full street addresses.
6. **Create only a marked test order.** Select a disposable product ID from
   the `get_products` response and run:

   ```powershell
   $productId = [int](Read-Host "Enter the disposable WooCommerce product ID")
   $testOrder = Invoke-UrumiMcp -RpcMethod "tools/call" -Params @{
     name = "woocommerce__create_order"
     arguments = @{ product_id = $productId; quantity = 1; test_order = $true }
   }
   $testOrder.result
   ```

   The tool rejects omitted/false test flags, takes no customer details, and
   never marks an order paid. It returns success only when WooCommerce confirms
   the pending/unpaid state and marker. Verify `test_order: true` and
   `_urumi_test_order` in WooCommerce Admin. If the response says to inspect the
   store, do that before retrying; the POST may already have created an order.
   Do not use a real customer or production store.
7. **Verify permissions and audit.** In the dashboard Team UI, use a test
   MEMBER key. Without grants, confirm WooCommerce tools are omitted and a
   direct call returns `isError: true`. Grant one read-only tool, verify it
   appears and works, then revoke that grant. Confirm the admin still has
   access and inspect `/api/audit?limit=20` for attributed successful and
   denied calls. Do not print API keys.
8. **Check NetworkPolicies.** Run `kubectl get networkpolicies -o wide` and
   inspect selectors/ports with `kubectl describe networkpolicy`. On the
   disposable cluster, test one expected allowed and one denied pod connection.
   YAML presence alone is not proof: record the CNI and observed results.
9. **Check persistence only with approval.** On the disposable cluster only,
   after recording the product/order IDs, run
   `kubectl rollout restart deployment/mysql deployment/wordpress`, wait with
   `kubectl rollout status deployment/mysql` and
   `kubectl rollout status deployment/wordpress`, then confirm the records
   remain. Never delete PVCs or restart shared/production workloads.
