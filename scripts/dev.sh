#!/usr/bin/env bash
# Local k3d bring-up: builds images, imports them, installs the chart.
set -euo pipefail
cd "$(dirname "$0")/.."
context="k3d-urumi"
if k3d cluster list urumi >/dev/null 2>&1; then
  if ! kubectl --context "$context" get --raw=/readyz >/dev/null 2>&1; then
    echo "Refusing deployment: the existing k3d cluster is not reachable as context $context." >&2
    exit 1
  fi
  release="$(helm list --filter '^urumi$' --namespace default --kube-context "$context" --short)"
  if [[ -n "$release" ]]; then
    echo "WARNING: this will upgrade the existing urumi release in namespace default on $context." >&2
    echo "The upgrade can change Secrets, NetworkPolicies, workloads, and other chart resources." >&2
    echo "Review the rendered changes and confirm the target cluster is disposable before proceeding." >&2
    if [[ ! -t 0 ]]; then
      echo "Refusing non-interactive upgrade of an existing release." >&2
      exit 1
    fi
    read -r -p "Type 'upgrade urumi in k3d-urumi/default' to continue: " confirmation
    if [[ "$confirmation" != "upgrade urumi in k3d-urumi/default" ]]; then
      echo "Upgrade cancelled." >&2
      exit 1
    fi
  fi
else
  echo "A new local k3d cluster will be created; chart resources will be installed into it."
fi
llm_key_file="$(mktemp)"
chmod 600 "$llm_key_file"
trap 'rm -f -- "$llm_key_file"' EXIT
if [[ -n "${LLM_API_KEY:-}" ]]; then
  printf '%s' "$LLM_API_KEY" > "$llm_key_file"
fi
k3d cluster list urumi >/dev/null 2>&1 || k3d cluster create urumi -p "80:80@loadbalancer"
for s in gateway woo-mcp weather-mcp currency-mcp; do docker build -t urumi/$s:latest services/$s; done
docker build -t urumi/dashboard:latest dashboard
k3d image import -c urumi urumi/gateway:latest urumi/woo-mcp:latest urumi/weather-mcp:latest urumi/currency-mcp:latest urumi/dashboard:latest
helm upgrade --install urumi infrastructure/helm/urumi --kube-context "$context" --namespace default -f infrastructure/helm/urumi/values.yaml -f infrastructure/helm/urumi/values-local.yaml --set-file "secrets.llmApiKey=$llm_key_file"
echo "Add to /etc/hosts:  127.0.0.1 store.urumi.local dashboard.urumi.local"
echo "Dashboard: http://dashboard.urumi.local (sign in with the Gateway admin API key from your secure setup)"
