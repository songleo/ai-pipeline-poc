#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"

for pid_file in "$PROJECT_ROOT"/.port-forward-*.pid; do
  [[ -e "$pid_file" ]] || continue
  pid="$(cat "$pid_file")"
  command_line="$(ps -p "$pid" -o args= 2>/dev/null || true)"
  if [[ "$command_line" == *"kubectl --context $EXPECTED_CONTEXT"*"port-forward"* ]]; then
    kill "$pid" 2>/dev/null || true
  elif [[ -n "$command_line" ]]; then
    echo "Skipping stale PID $pid; it is not an $EXPECTED_CONTEXT port-forward." >&2
  fi
  rm -f -- "$pid_file"
done
if kind get clusters | grep -Fxq "$CLUSTER_NAME"; then
  kind delete cluster --name "$CLUSTER_NAME"
else
  echo "Kind cluster $CLUSTER_NAME does not exist; nothing to delete."
fi
