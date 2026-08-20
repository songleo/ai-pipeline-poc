#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER_NAME="ssli-demo"
EXPECTED_CONTEXT="kind-ssli-demo"
NAMESPACE="pipeline-demo"
IMAGE_TAG="0.1.0"

require_context() {
  local context
  context="$(kubectl config current-context 2>/dev/null || true)"
  if [[ "$context" != "$EXPECTED_CONTEXT" ]]; then
    echo "Refusing Kubernetes operation: current context is '$context', expected '$EXPECTED_CONTEXT'." >&2
    exit 1
  fi
}
