#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"

PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"
docker build --provenance=false --build-arg "PIP_INDEX_URL=$PIP_INDEX_URL" -t "ssli-demo-backend:$IMAGE_TAG" "$PROJECT_ROOT/backend"
docker build --provenance=false --build-arg "NPM_REGISTRY=$NPM_REGISTRY" -t "ssli-demo-frontend:$IMAGE_TAG" "$PROJECT_ROOT/frontend"
kind load docker-image --name "$CLUSTER_NAME" \
  "ssli-demo-backend:$IMAGE_TAG" \
  "ssli-demo-frontend:$IMAGE_TAG"
