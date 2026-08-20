#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_context

k="kubectl --context $EXPECTED_CONTEXT"
$k apply -f "$PROJECT_ROOT/deploy/namespace/namespace.yaml"
$k apply -f "$PROJECT_ROOT/deploy/rbac/rbac.yaml"
$k apply -f "$PROJECT_ROOT/deploy/argo/workflow-templates/pipeline-demo-nodes.yaml"
$k apply -f "$PROJECT_ROOT/deploy/app/backend.yaml"
$k apply -f "$PROJECT_ROOT/deploy/app/frontend.yaml"
$k -n "$NAMESPACE" rollout status deployment/pipeline-demo-backend --timeout=180s
$k -n "$NAMESPACE" rollout status deployment/pipeline-demo-frontend --timeout=180s
$k -n "$NAMESPACE" get deploy,pod,svc,workflowtemplate
