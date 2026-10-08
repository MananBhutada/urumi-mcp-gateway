#!/usr/bin/env bash
# Local k3d bring-up: builds images, imports them, installs the chart.
set -euo pipefail
cd "$(dirname "$0")/.."
k3d cluster list urumi >/dev/null 2>&1 || k3d cluster create urumi -p "80:80@loadbalancer"
for s in gateway woo-mcp weather-mcp currency-mcp; do docker build -t urumi/$s:latest services/$s; done
docker build -t urumi/dashboard:latest dashboard
k3d image import -c urumi urumi/gateway:latest urumi/woo-mcp:latest urumi/weather-mcp:latest urumi/currency-mcp:latest urumi/dashboard:latest
helm upgrade --install urumi infrastructure/helm/urumi -f infrastructure/helm/urumi/values-local.yaml --set secrets.anthropicApiKey="${ANTHROPIC_API_KEY:-}"
echo "Add to /etc/hosts:  127.0.0.1 store.urumi.local dashboard.urumi.local"
echo "Dashboard: http://dashboard.urumi.local  (admin key = secrets.bootstrapAdminKey)"
