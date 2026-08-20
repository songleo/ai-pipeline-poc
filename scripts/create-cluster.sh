#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"

NODE_IMAGE="${KIND_NODE_IMAGE:-kindest/node:v1.33.1@sha256:050072256b9a903bd914c0b2866828150cb229cea0efe5892e2b644d5dd3b34f}"
if kind get clusters | grep -Fxq "$CLUSTER_NAME"; then
  echo "Kind cluster $CLUSTER_NAME already exists."
else
  kind create cluster --name "$CLUSTER_NAME" --image "$NODE_IMAGE" --wait 120s
fi
kubectl config use-context "$EXPECTED_CONTEXT" >/dev/null
require_context
kubectl cluster-info --context "$EXPECTED_CONTEXT"
