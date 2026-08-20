#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_context

ARGO_CHART_VERSION="1.0.23"
ARGO_CHART_SHA256="a20365b94f3c286eed01c1ca7bd1ec428efa002f5610f140dd4c933322d6bc6d"
ARGO_CHART_URL="${ARGO_CHART_URL:-https://ghfast.top/https://github.com/argoproj/argo-helm/releases/download/argo-workflows-${ARGO_CHART_VERSION}/argo-workflows-${ARGO_CHART_VERSION}.tgz}"
ARGO_CHART_ARCHIVE="${ARGO_CHART_ARCHIVE:-$PROJECT_ROOT/.cache/argo-workflows-${ARGO_CHART_VERSION}.tgz}"

mkdir -p "$(dirname "$ARGO_CHART_ARCHIVE")"
if [[ ! -f "$ARGO_CHART_ARCHIVE" ]] || ! echo "$ARGO_CHART_SHA256  $ARGO_CHART_ARCHIVE" | sha256sum -c - >/dev/null 2>&1; then
  curl -fL --retry 3 --connect-timeout 15 -o "$ARGO_CHART_ARCHIVE" "$ARGO_CHART_URL"
fi
echo "$ARGO_CHART_SHA256  $ARGO_CHART_ARCHIVE" | sha256sum -c -

helm upgrade --install argo-workflows "$ARGO_CHART_ARCHIVE" \
  --namespace argo --create-namespace \
  --set server.authModes[0]=server \
  --wait --timeout 10m \
  --kube-context "$EXPECTED_CONTEXT"
kubectl --context "$EXPECTED_CONTEXT" -n argo rollout status deployment/argo-workflows-workflow-controller --timeout=180s
kubectl --context "$EXPECTED_CONTEXT" -n argo rollout status deployment/argo-workflows-server --timeout=180s
helm --kube-context "$EXPECTED_CONTEXT" -n argo list
