# Store deployment runbook (local k3d)

This runbook is the next execution gate for the Urumi take-home. Passing unit tests or rendering Helm templates is **not** proof that WooCommerce, checkout, or persistence works. Record actual output and keep the acceptance checklist honest.

## 1. Prerequisites

Install Docker Desktop, `kubectl`, `helm` (3.16+), and `k3d`. On Windows, run commands in PowerShell from the repository root. Ensure Docker Desktop is running.

Check versions:

```powershell
docker version
kubectl version --client
helm version
k3d version
```

## 2. Validate the chart before creating a cluster

```powershell
helm lint infrastructure/helm/urumi -f infrastructure/helm/urumi/values-local.yaml
helm lint infrastructure/helm/urumi -f infrastructure/helm/urumi/values-prod.yaml
helm template urumi infrastructure/helm/urumi -f infrastructure/helm/urumi/values-local.yaml
helm template urumi infrastructure/helm/urumi -f infrastructure/helm/urumi/values-prod.yaml
```

The CI workflow runs these same lint/render gates and asserts that the rendered output includes Deployments, Ingress, Secret resources, and all three database/content PVCs. This checks chart syntax and expected resources only; it does not install the chart.

## 3. Build and install

Use only disposable local values for a local cluster. Never copy local demo credentials into production.

```powershell
./scripts/dev.sh
```

If PowerShell cannot run the shell script, use Git Bash or WSL. The script creates a k3d cluster if needed, builds the service images, imports them, and installs/upgrades the chart.

Then inspect actual cluster state:

```powershell
kubectl get pods -o wide
kubectl get jobs
kubectl get pvc
kubectl get ingress
kubectl describe job wp-setup
kubectl logs job/wp-setup
```

Do not continue until MySQL and WordPress are Ready, the setup Job has completed successfully, and the MySQL, WordPress, and PostgreSQL claims are Bound. If a Job failed, inspect its logs and events before deleting or retrying it.

Add the local hostnames to the Windows hosts file as administrator:

```text
127.0.0.1 store.urumi.local dashboard.urumi.local
```

Open `http://store.urumi.local` and `http://dashboard.urumi.local`.

## 4. Prove real store behavior

1. Confirm the Sample Tee product is published and visible in the storefront.
2. Add it to the cart and complete checkout with Cash on Delivery using test-only customer data.
3. Sign into `/wp-admin` and verify the order number, line items, amount, payment method and initial status.
4. Set `WOO_BASE_URL`, `WOO_CONSUMER_KEY`, and `WOO_CONSUMER_SECRET` in the terminal, then run `python scripts/smoke_test_woocommerce.py`.
5. Set `WOO_TEST_ORDER_ID` to a disposable test order to exercise get-order and same-status update behavior.
6. Confirm all five WooCommerce MCP tools through the gateway, not by calling the upstream from the dashboard/client.
7. Record the product and order IDs before restarting pods.

## 5. Prove persistence

Find the actual WordPress and MySQL pod names with `kubectl get pods`, then delete those pods (not the PVCs):

```powershell
kubectl delete pod -l app=wordpress
kubectl delete pod -l app=mysql
kubectl get pods -w
```

After both become Ready, re-open the storefront and wp-admin. The previously recorded product and order must still exist. Never delete PVCs as part of this test.

## 6. Troubleshooting guide

- **wp-setup is Pending:** inspect pod events and PVC access mode / scheduling.
- **wp-setup is BackOff:** inspect `kubectl logs job/wp-setup`; confirm WordPress has initialized `wp-config.php`, MySQL is ready, and the CLI container can mount the WordPress volume.
- **Store redirects to the wrong scheme/host:** check `wordpress.scheme`, `ingress.storeHost`, and forwarded-proto handling.
- **REST smoke test gets 401/403:** verify the WooCommerce API key has the intended permissions and that the exact consumer key/secret are injected into the Woo MCP container.
- **REST smoke test cannot connect:** verify service DNS and that the configured base URL is reachable from inside the cluster. Do not expose MySQL or the Woo MCP publicly to work around networking.
- **Products/orders vanish after restart:** stop and inspect PVC bindings and mount paths; do not mark persistence passed.

## 7. Completion record

Only mark each gate complete when observed. Save:
- Helm lint/template output
- `kubectl get pods,jobs,pvc,ingress` output
- wp-setup Job logs
- storefront checkout order ID and wp-admin verification
- REST smoke-test output (never credentials)
- post-restart product/order verification

Production-like k3s/VPS deployment is a separate gate; local k3d success does not prove production deployment.
