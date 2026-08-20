#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_context

start_forward() {
  local name="$1"
  local namespace="$2"
  local resource="$3"
  local ports="$4"
  local pid_file="$PROJECT_ROOT/.port-forward-$name.pid"
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    if [[ "${PORT_FORWARD_RESTART:-0}" == "1" ]]; then
      kill "$(cat "$pid_file")"
    else
      echo "$name port-forward already running (PID $(cat "$pid_file"))."
      return
    fi
  fi
  nohup kubectl --context "$EXPECTED_CONTEXT" -n "$namespace" port-forward --address 0.0.0.0 "$resource" "$ports" \
    </dev/null >"$PROJECT_ROOT/$name-port-forward.log" 2>&1 &
  echo $! >"$pid_file"
}

start_forward frontend "$NAMESPACE" service/pipeline-demo-frontend 5173:8080
start_forward backend "$NAMESPACE" service/pipeline-demo-backend 8000:8000
start_forward argo argo service/argo-workflows-server 2746:2746
echo "Demo: http://localhost:5173"
echo "API:  http://localhost:8000/api/health"
echo "Argo: http://localhost:2746"
wsl_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [[ -n "$wsl_ip" ]]; then
  echo "Windows fallback: http://$wsl_ip:5173 (API :8000, Argo :2746)"
fi
