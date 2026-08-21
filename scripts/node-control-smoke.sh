#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_context
command -v jq >/dev/null 2>&1 || { echo "Missing required tool: jq" >&2; exit 1; }

API_URL="${API_URL:-http://localhost:5173}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf -- "$TMP_DIR"' EXIT

python3 - "$PROJECT_ROOT/examples/training-qualification-pipeline.json" "$TMP_DIR/node-control.json" <<'PY'
import json,sys
value=json.load(open(sys.argv[1],encoding="utf-8"))
value["metadata"]["name"]="node-control-smoke"
value["metadata"]["tags"].append("system-test")
value["spec"]["runPolicy"]["timeoutSeconds"]=600
for node in value["spec"]["nodes"]:
    if node["id"] in {"train-baseline","train-candidate"}:
        node["parameters"]["durationSeconds"]=30
    elif "durationSeconds" in node["parameters"]:
        node["parameters"]["durationSeconds"]=1
json.dump(value,open(sys.argv[2],"w",encoding="utf-8"))
PY

workflow="$(curl -fsS -H 'Content-Type: application/json' --data-binary "@$TMP_DIR/node-control.json" "$API_URL/api/runs" | jq -er '.workflowName')"
echo "Submitted $workflow"

deadline=$((SECONDS + 150))
while (( SECONDS < deadline )); do
  run="$(curl -fsS "$API_URL/api/runs/$workflow")"
  a="$(jq -r '.nodes[] | select(.nodeId=="train-baseline") | .status' <<<"$run")"
  b="$(jq -r '.nodes[] | select(.nodeId=="train-candidate") | .status' <<<"$run")"
  [[ "$a" == "RUNNING" && "$b" == "RUNNING" ]] && break
  sleep 2
done
[[ "${a:-}" == "RUNNING" && "${b:-}" == "RUNNING" ]]
curl -fsS -X POST "$API_URL/api/runs/$workflow/nodes/train-baseline/stop" | jq -e '.controlState=="STOP_REQUESTED"' >/dev/null

deadline=$((SECONDS + 150))
while (( SECONDS < deadline )); do
  run="$(curl -fsS "$API_URL/api/runs/$workflow")"
  [[ "$(jq -r '.status' <<<"$run")" == "FAILED" ]] && break
  sleep 2
done
jq -e '(.status=="FAILED") and (.nodes[] | select(.nodeId=="train-baseline") | .status=="CANCELLED" and .retryCount==0)' <<<"$run" >/dev/null
jq -e '.nodes[] | select(.nodeId=="train-candidate") | .status=="SUCCEEDED"' <<<"$run" >/dev/null
train_b_started="$(jq -r '.nodes[] | select(.nodeId=="train-candidate") | .startedAt' <<<"$run")"
curl -fsS "$API_URL/api/runs/$workflow/nodes/train-baseline/logs" | grep -q 'stop requested'

curl -fsS -X POST "$API_URL/api/runs/$workflow/nodes/train-baseline/rerun" | jq -e '.status=="PENDING"' >/dev/null
deadline=$((SECONDS + 180))
while (( SECONDS < deadline )); do
  run="$(curl -fsS "$API_URL/api/runs/$workflow")"
  [[ "$(jq -r '.status' <<<"$run")" == "SUCCEEDED" ]] && break
  sleep 2
done
jq -e --arg started "$train_b_started" '(.status=="SUCCEEDED") and (.nodes[] | select(.nodeId=="train-candidate") | .startedAt==$started)' <<<"$run" >/dev/null
jq -e '.nodes[] | select(.nodeId=="train-baseline" or .nodeId=="leaderboard" or .nodeId=="admission" or .nodeId=="register" or .nodeId=="inference-smoke" or .nodeId=="deployment") | .status=="SUCCEEDED"' <<<"$run" >/dev/null

echo "Node control smoke passed: baseline training stopped without retry, candidate training continued, and the selected branch reran successfully."
